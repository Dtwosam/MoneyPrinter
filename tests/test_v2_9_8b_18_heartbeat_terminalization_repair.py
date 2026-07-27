"""Focused disposable proof for V2-9.8B.18; no network or authoritative DB."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import campaign_supervision as supervision
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    persist_campaign_heartbeat_failure,
    renew_campaign_lease,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.heartbeat_terminalization_recovery import (
    CAMPAIGN_ID,
    CAMPAIGN_RUN_ID,
    CONFIGURATION_ID,
    CYCLE_ID,
    EXECUTION_ID,
    FACTORY_RUN_ID,
    ORIGINAL_REPORT_ID,
    OWNER_ID,
    RECOVERY_REPORT_ID,
    SLOTS,
    SUPERVISION_ID,
    TERMINAL_CAUSE,
    recover_exact_heartbeat_terminal_residue,
)
from printer_v1.operator_cli.one_command_15m_factory import (
    run_one_command_15m_factory,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_campaign_terminal_report,
    reconcile_campaign_terminal,
    write_campaign_terminal_report,
)


NOW = datetime(2026, 7, 27, 20, 0, 0, tzinfo=timezone.utc)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW.isoformat(),
    }


def _seed_running_graph(
    db: Path,
    *,
    campaign_id: str = "campaign",
    configuration_id: str = "configuration",
    run_id: str = "campaign-run",
) -> sqlite3.Connection:
    create_campaign(
        db,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        configuration={"slots": 2},
        launch_provenance=_provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="fixture",
        proof_source_db_identity="fixture-source",
        policy_version="v2-9.8b.18",
    )
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        run_ordinal=1,
        now=NOW.isoformat(),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING' "
        "WHERE campaign_id=?", (campaign_id,),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING' "
        "WHERE run_id=?", (run_id,),
    )
    connection.commit()
    return connection


class HeartbeatEvidenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db = self.root / "heartbeat.sqlite3"
        apply_migrations(self.db)
        self.connection = _seed_running_graph(self.db)
        self.lock = self.root / "campaign.lease.json"
        acquire_campaign_supervision(
            self.db,
            lock_path=self.lock,
            supervision_id="supervision",
            campaign_id="campaign",
            configuration_id="configuration",
            run_id="campaign-run",
            owner_id="owner",
            lease_seconds=30,
            now=NOW,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def _renew(self, instant: datetime) -> dict[str, object]:
        return renew_campaign_lease(
            self.db,
            supervision_id="supervision",
            campaign_id="campaign",
            configuration_id="configuration",
            run_id="campaign-run",
            owner_id="owner",
            lease_seconds=30,
            now=instant,
        )

    def test_successful_heartbeat_renewal_advances_both_times(self) -> None:
        result = self._renew(NOW + timedelta(seconds=10))
        self.assertTrue(result["renewal_confirmed"])
        connection = sqlite3.connect(self.db)
        row = connection.execute(
            "SELECT heartbeat_at,lease_expires_at FROM "
            "printer_memory_factory_campaign_supervision"
        ).fetchone()
        failure_count = connection.execute(
            "SELECT COUNT(*) FROM "
            "printer_memory_factory_campaign_heartbeat_failures"
        ).fetchone()[0]
        connection.close()
        self.assertEqual(row[0], (NOW + timedelta(seconds=10)).isoformat())
        self.assertEqual(row[1], (NOW + timedelta(seconds=40)).isoformat())
        self.assertEqual(failure_count, 0)

    def test_sqlite_lock_failure_uses_lease_fallback_then_durable_ledger(self) -> None:
        blocker = sqlite3.connect(self.db, timeout=0.0)
        blocker.execute("BEGIN IMMEDIATE")
        try:
            with (
                patch.object(supervision, "SQLITE_BUSY_TIMEOUT_SECONDS", 0.01),
                patch.object(supervision, "SQLITE_BUSY_MAX_ATTEMPTS", 1),
            ):
                result = self._renew(NOW + timedelta(seconds=10))
        finally:
            blocker.rollback()
            blocker.close()
        self.assertFalse(result["renewal_confirmed"])
        self.assertTrue(result["sqlite_locked"])
        self.assertEqual(result["durable_evidence_location"], "LEASE_FILE")
        lease_payload = json.loads(self.lock.read_text(encoding="utf-8"))
        self.assertEqual(
            lease_payload["first_heartbeat_renewal_failure"]["terminal_cause"],
            "LEASE_RENEWAL_SQLITE_LOCKED",
        )
        persisted = persist_campaign_heartbeat_failure(
            self.db,
            supervision_id="supervision",
            campaign_id="campaign",
            configuration_id="configuration",
            run_id="campaign-run",
            owner_id="owner",
            evidence=dict(result["failure_evidence"]),
        )
        self.assertTrue(persisted["persisted"])
        connection = sqlite3.connect(self.db)
        row = connection.execute(
            "SELECT safe_error_category,sqlite_locked,prior_heartbeat_at,"
            "prior_lease_expires_at,renewal_confirmed FROM "
            "printer_memory_factory_campaign_heartbeat_failures"
        ).fetchone()
        connection.close()
        self.assertEqual(
            tuple(row),
            (
                "SQLITE_LOCK_CONTENTION", 1, NOW.isoformat(),
                (NOW + timedelta(seconds=30)).isoformat(), 0,
            ),
        )

    def test_expired_lease_failure_is_durable_and_truthful(self) -> None:
        result = self._renew(NOW + timedelta(seconds=31))
        self.assertFalse(result["renewal_confirmed"])
        self.assertFalse(result["sqlite_locked"])
        self.assertEqual(result["renewal_error_category"], "LEASE_EXPIRED")
        self.assertEqual(
            result["suggested_terminal_cause"], "LEASE_RENEWAL_LEASE_EXPIRED"
        )
        self.assertEqual(result["durable_evidence_location"], "SQLITE")

    def test_failure_message_is_redacted_and_first_failure_is_immutable(self) -> None:
        with patch.object(
            supervision,
            "_replace_lock",
            side_effect=OSError("api_key=secret-value"),
        ):
            result = self._renew(NOW + timedelta(seconds=10))
        rendered = json.dumps(result, sort_keys=True)
        self.assertNotIn("secret-value", rendered)
        self.assertNotIn("api_key", rendered)
        self.assertEqual(result["renewal_error_category"], "LEASE_RENEWAL_ERROR")
        changed = dict(result["failure_evidence"])
        changed["attempted_at"] = (NOW + timedelta(seconds=11)).isoformat()
        with self.assertRaisesRegex(
            supervision.CampaignSupervisionError, "immutable"
        ):
            persist_campaign_heartbeat_failure(
                self.db,
                supervision_id="supervision",
                campaign_id="campaign",
                configuration_id="configuration",
                run_id="campaign-run",
                owner_id="owner",
                evidence=changed,
            )


class ImmediateCancellationTests(unittest.TestCase):
    def test_post_creation_cancellation_closes_zero_step_factory_and_keeps_id(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "proof.sqlite3"
            backup = root / "proof.backup.sqlite3"
            apply_migrations(db)
            shutil.copyfile(db, backup)
            initialized: list[str] = []
            result = run_one_command_15m_factory(
                db,
                backup,
                operator_approved=True,
                proof_mode=True,
                launch_provenance=_provenance(),
                project_root=root,
                cancellation_probe=lambda: "LEASE_RENEWAL_SQLITE_LOCKED",
                factory_run_initialized=initialized.append,
                discovery_runner=lambda _args: self.fail("discovery must not run"),
                _sleep=lambda _seconds: None,
            )
            self.assertEqual(len(initialized), 1)
            self.assertEqual(result["run_id"], initialized[0])
            self.assertEqual(result["stop_reason"], "LEASE_RENEWAL_SQLITE_LOCKED")
            connection = sqlite3.connect(db)
            row = connection.execute(
                "SELECT run_status,stop_reason FROM printer_memory_factory_runs "
                "WHERE run_id=?", (initialized[0],),
            ).fetchone()
            steps = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps WHERE run_id=?",
                (initialized[0],),
            ).fetchone()[0]
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
            connection.close()
            self.assertNotEqual(row[0], "RUNNING")
            self.assertEqual(row[1], "LEASE_RENEWAL_SQLITE_LOCKED")
            self.assertEqual(steps, 0)
            self.assertEqual(integrity, "ok")
            self.assertEqual(foreign_keys, [])


def _seed_exact_recovery_fixture(db: Path, artifact_root: Path) -> None:
    apply_migrations(db)
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    for token_id in (20, 21):
        connection.execute(
            "INSERT INTO printer_tokens(id,token_mint,token_status) VALUES (?,?,?)",
            (token_id, f"mint-{token_id}", "TRACK_NORMAL"),
        )
    for pair_id, token_id in ((24, 20), (25, 21)):
        connection.execute(
            "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
            "VALUES (?,?,?,?)",
            (pair_id, token_id, f"pair-{pair_id}", f"mint-{token_id}"),
        )
    for _slot, _ordinal, token_id, pair_id, queue_id in SLOTS:
        connection.execute(
            """INSERT INTO printer_tracking_queue(
                   id,token_id,pair_id,tracking_lane,tracking_action,
                   priority_reason,queue_status,source_status,data_quality_label)
               VALUES (?,?,?,'TRACK_NORMAL','PROMOTE_TO_TRACK_NORMAL',
                       'fixture','QUEUED','COMPLETE','CLEAN_DATA')""",
            (queue_id, token_id, pair_id),
        )
    connection.commit()
    connection.close()
    create_campaign(
        db,
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        configuration={"execution_id": EXECUTION_ID, "slots": 2},
        launch_provenance=_provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="exact-recovery-fixture",
        proof_source_db_identity="fixture-source",
        policy_version="v2-9.8b.18",
    )
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    create_campaign_run(
        connection,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        run_ordinal=1,
        now=NOW.isoformat(),
    )
    create_cycle_with_two_slots(
        connection,
        campaign_id=CAMPAIGN_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        cycle_ordinal=1,
        slots=[
            {
                "token_slot_id": slot_id,
                "slot_ordinal": ordinal,
                "token_identity": f"token-{token_id}",
                "token_row_id": token_id,
                "mint_identity": f"mint-{token_id}",
                "pair_identity": f"pair-{pair_id}",
                "pair_row_id": pair_id,
                "lifecycle_identity": f"lifecycle-{token_id}",
                "tracking_queue_id": queue_id,
            }
            for slot_id, ordinal, token_id, pair_id, queue_id in SLOTS
        ],
        now=NOW.isoformat(),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING' "
        "WHERE campaign_id=?", (CAMPAIGN_ID,),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING' "
        "WHERE run_id=?", (CAMPAIGN_RUN_ID,),
    )
    connection.execute(
        """INSERT INTO printer_memory_factory_runs(
               run_id,run_status,window_kind,db_mode,config_hash,config_json,
               selected_token_count,started_at,created_at,updated_at)
           VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','fixture','{}',0,?,?,?)""",
        (FACTORY_RUN_ID, NOW.isoformat(), NOW.isoformat(), NOW.isoformat()),
    )
    connection.commit()
    connection.close()
    lock = artifact_root / "exact.lease.json"
    acquire_campaign_supervision(
        db,
        lock_path=lock,
        supervision_id=SUPERVISION_ID,
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        run_id=CAMPAIGN_RUN_ID,
        owner_id=OWNER_ID,
        lease_seconds=30,
        now=NOW,
    )
    cleanup_campaign_supervision(
        db,
        supervision_id=SUPERVISION_ID,
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        run_id=CAMPAIGN_RUN_ID,
        owner_id=OWNER_ID,
        terminal_status="FAILED",
        first_terminal_cause="OPERATIONAL_CAMPAIGN_FAILED:_ExternalStop",
        now=NOW + timedelta(minutes=2),
    )
    bad_report = build_campaign_terminal_report(
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        run_id=CAMPAIGN_RUN_ID,
        cycle_id=CYCLE_ID,
        report_id=ORIGINAL_REPORT_ID,
        factory_run_id=None,
        execution_id=EXECUTION_ID,
        terminal_status="FAILED",
        terminal_cause="OPERATIONAL_CAMPAIGN_FAILED:_ExternalStop",
        run_status="FAILED",
        lifecycle_started=False,
        reconciliation={"factory_run": "not_found"},
        forbidden_deltas={},
        launch_git_provenance=_provenance(),
    )
    write_campaign_terminal_report(
        db,
        artifact_root / "reports",
        report_id=ORIGINAL_REPORT_ID,
        campaign_id=CAMPAIGN_ID,
        configuration_id=CONFIGURATION_ID,
        report=bad_report,
        now=NOW,
    )


class TerminalReconciliationAndRecoveryTests(unittest.TestCase):
    def test_exact_recovery_is_truthful_safe_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "authoritative-fixture.sqlite3"
            artifacts = root / "execution-artifacts"
            artifacts.mkdir()
            _seed_exact_recovery_fixture(db, artifacts)
            before = sqlite3.connect(db)
            locked_before = {
                table: before.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in LOCKED_CAPABILITY_TABLES
            }
            before.close()
            first = recover_exact_heartbeat_terminal_residue(
                operator_approved=True,
                db_path=db,
                artifact_root=artifacts,
                recovery_root=root / "fresh-recovery-backup",
                process_probe=lambda: False,
                now=NOW + timedelta(minutes=3),
            )
            self.assertEqual(first["status"], "RECOVERED")
            self.assertEqual(first["factory_run_id"], FACTORY_RUN_ID)
            self.assertEqual(first["factory_run_status"], "SAFE_STOPPED")
            self.assertEqual(first["terminal_cause"], TERMINAL_CAUSE)
            self.assertEqual(first["source_calls"], 0)
            self.assertEqual(first["scheduler_runtime_calls"], 0)
            self.assertFalse(first["retry_created"])
            self.assertFalse(first["restart_created"])
            self.assertFalse(first["successor_created"])
            self.assertTrue(Path(first["backup_path"]).is_file())
            self.assertTrue(Path(first["report_artifact"]).is_file())

            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            locked_after = {
                table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
                for table in LOCKED_CAPABILITY_TABLES
            }
            report = json.loads(connection.execute(
                "SELECT report_json FROM printer_memory_factory_campaign_reports "
                "WHERE report_id=?", (RECOVERY_REPORT_ID,),
            ).fetchone()[0])
            self.assertEqual(
                report["identity"]["factory_run_id"], FACTORY_RUN_ID
            )
            self.assertEqual(report["reconciliation"]["factory_run"], "SAFE_STOPPED")
            self.assertEqual(locked_before, locked_after)
            self.assertEqual(connection.execute(
                "PRAGMA integrity_check"
            ).fetchone()[0], "ok")
            self.assertEqual(connection.execute(
                "PRAGMA foreign_key_check"
            ).fetchall(), [])
            connection.close()

            second = recover_exact_heartbeat_terminal_residue(
                operator_approved=True,
                db_path=db,
                artifact_root=artifacts,
                recovery_root=root / "must-not-be-created",
                process_probe=lambda: False,
                now=NOW + timedelta(minutes=4),
            )
            self.assertEqual(second["status"], "ALREADY_RECOVERED_IDEMPOTENT")
            self.assertEqual(second["database_writes"], 0)
            self.assertFalse((root / "must-not-be-created").exists())


if __name__ == "__main__":
    unittest.main()
