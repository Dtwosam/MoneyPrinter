"""V2-9.8B.19 full production readiness consolidation disposable proofs.

Fixture sources and disposable databases only. No production campaign, no live
network, no retrieval/financial activation, no authoritative mutation.
"""

from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db.migrate import (
    apply_migrations,
    canonical_migration_count,
    canonical_migration_names,
    describe_migration_ledger_mismatch,
    validate_migration_ledger,
)
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    persist_campaign_heartbeat_failure,
    renew_campaign_lease,
)
from printer_v1.operator_cli.campaign_ownership import (
    create_campaign_run,
    create_cycle_with_two_slots,
)
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_OPERATIONAL_PERSISTENT,
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.operational_backup_restore_preflight import (
    operational_backup_restore_preflight,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    assemble_campaign_terminal_reporting,
    build_campaign_terminal_report,
    reconcile_campaign_terminal,
    replay_campaign_terminal_report,
    write_campaign_terminal_report,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITATIVE = ROOT / "data" / "printer_v1.sqlite3"
NOW = "2026-07-27T21:00:00+00:00"


def _provenance() -> dict[str, object]:
    return {
        "git_head": "b" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW,
    }


class _Dependency:
    status = "READY"

    def to_dict(self):
        return {"status": "READY", "external_requests": 0, "database_writes": 0}


def _copy_authoritative_corpus(destination: Path) -> None:
    if not AUTHORITATIVE.is_file():
        raise unittest.SkipTest("authoritative corpus unavailable")
    shutil.copy2(AUTHORITATIVE, destination)


def _quiesce_operational_surfaces(db: Path) -> None:
    connection = sqlite3.connect(db)
    try:
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute(
            """
            UPDATE printer_scheduler_jobs
            SET status='CANCELLED',
                finished_at=COALESCE(finished_at, ?),
                updated_at=?,
                locked_at=NULL,
                lock_owner=NULL
            WHERE status IN ('PENDING', 'RUNNING')
               OR locked_at IS NOT NULL
               OR lock_owner IS NOT NULL
            """,
            (NOW, NOW),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaigns
            SET campaign_state='TERMINAL_COMPLETED', updated_at=?
            WHERE campaign_state IN ('PREFLIGHT', 'RUNNING', 'STOP_REQUESTED', 'DRAFT')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaign_runs
            SET run_state='TERMINAL_COMPLETED', updated_at=?
            WHERE run_state IN ('RUNNING', 'STOP_REQUESTED')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_campaign_supervision
            SET supervision_state='TERMINAL',
                terminal_status=COALESCE(terminal_status, 'COMPLETED'),
                updated_at=?
            WHERE supervision_state IN ('ACTIVE', 'STOPPING')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_discovery_work
            SET work_state='TERMINAL', updated_at=?
            WHERE work_state IN ('PENDING', 'RUNNING', 'COOLDOWN')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_memory_factory_run_steps
            SET step_status='SKIPPED', updated_at=?
            WHERE step_status IN ('PENDING', 'RUNNING')
            """,
            (NOW,),
        )
        connection.execute(
            """
            UPDATE printer_proof_run_supervision
            SET execution_status='TERMINAL', updated_at=?
            WHERE execution_status IN ('STARTING', 'RUNNING')
            """,
            (NOW,),
        )
        connection.commit()
        foreign_keys = connection.execute("PRAGMA foreign_key_check").fetchall()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
        if foreign_keys or integrity != "ok":
            raise AssertionError(
                f"quiesced corpus unhealthy integrity={integrity} fks={foreign_keys[:5]}"
            )
    finally:
        connection.close()


class CanonicalMigrationLedgerTests(unittest.TestCase):
    def test_canonical_count_matches_directory_and_is_not_hardcoded_forty_four(self) -> None:
        names = canonical_migration_names()
        count = canonical_migration_count()
        self.assertEqual(count, len(names))
        self.assertEqual(count, command.EXPECTED_MIGRATION_COUNT)
        self.assertEqual(count, 45)
        self.assertTrue(names[-1].startswith("045"))
        self.assertEqual(names[-1], "045_heartbeat_failure_evidence.sql")
        # Stale hard-code must not reappear as the sole authority.
        self.assertNotEqual(command.EXPECTED_MIGRATION_COUNT, 44)

    def test_current_ledger_passes_and_corruptions_fail_with_exact_reasons(self) -> None:
        expected = list(canonical_migration_names())
        ok = validate_migration_ledger(expected)
        self.assertTrue(ok["matches"])
        self.assertEqual(ok["canonical_count"], 45)
        self.assertEqual(ok["latest_canonical"], expected[-1])

        missing = validate_migration_ledger(expected[:-1])
        self.assertFalse(missing["matches"])
        self.assertTrue(
            any("missing canonical migrations" in issue for issue in missing["issues"])
        )

        unexpected = validate_migration_ledger(expected + ["999_unexpected.sql"])
        self.assertFalse(unexpected["matches"])
        self.assertTrue(
            any("unexpected applied migrations" in issue for issue in unexpected["issues"])
        )

        reordered = list(expected)
        reordered[0], reordered[1] = reordered[1], reordered[0]
        reordered_report = validate_migration_ledger(reordered)
        self.assertFalse(reordered_report["matches"])
        self.assertTrue(
            any("reordered" in issue for issue in reordered_report["issues"])
        )

        duplicate = list(expected) + [expected[-1]]
        duplicate_issues = describe_migration_ledger_mismatch(duplicate)
        self.assertTrue(any("duplicate" in issue for issue in duplicate_issues))

    def test_apply_migrations_writes_exact_canonical_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "fresh.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            try:
                applied = [
                    str(row[0])
                    for row in connection.execute(
                        "SELECT version FROM printer_schema_migrations ORDER BY version"
                    )
                ]
            finally:
                connection.close()
            self.assertEqual(applied, list(canonical_migration_names()))
            self.assertEqual(len(applied), 45)


class ActionLocalBlockedCountersTests(unittest.TestCase):
    def test_blocked_preflight_never_copies_prior_campaign_source_total(self) -> None:
        stderr = io.StringIO()
        with patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "build_activation_preflight",
            side_effect=command.OperationalMemoryFactoryError(
                "operational preflight blocked: gate=migration_ledger: test"
            ),
        ), patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "_latest_campaign_source_total",
            return_value=22,
        ) as source_total, patch.object(sys, "stderr", stderr):
            code = command.main(["preflight-only"])
        self.assertEqual(code, 1)
        source_total.assert_not_called()
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["status"], "OPERATIONAL_COMMAND_BLOCKED")
        self.assertEqual(payload["mode"], "preflight-only")
        self.assertEqual(payload["source_calls"], 0)
        self.assertIsNone(payload["campaign_source_calls"])
        self.assertEqual(payload["scheduler_runtime_calls"], 0)
        self.assertEqual(payload["database_writes"], 0)
        self.assertIn("gate=migration_ledger", payload["error_message"])

    def test_blocked_run_reports_only_action_run_ledger(self) -> None:
        stderr = io.StringIO()

        def _failing_run(**_kwargs):
            command._ACTION_RUN_CONTEXT["run_id"] = "action-run-19"
            raise RuntimeError("disposable action fault")

        with patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "run_operational_campaign",
            side_effect=_failing_run,
        ), patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "_latest_campaign_source_total",
            return_value=7,
        ) as source_total, patch.object(sys, "stderr", stderr):
            code = command.main(["run", "--operator-approved"])
        self.assertEqual(code, 1)
        source_total.assert_called_once_with(run_id="action-run-19")
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["source_calls"], 7)
        self.assertEqual(payload["campaign_source_calls"], 7)
        self.assertEqual(payload["action_run_id"], "action-run-19")


class PreflightStatusReportZeroSurfaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db = self.root / "printer_v1.sqlite3"
        _copy_authoritative_corpus(self.db)
        _quiesce_operational_surfaces(self.db)
        self.provenance = _provenance()
        self.source_ready = {
            "status": "READY",
            "external_requests": 0,
            "secret_material_recorded": False,
        }

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_preflight_ready_migration_45_zero_source_zero_write(self) -> None:
        before = self.db.read_bytes()
        with (
            patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(
                command,
                "build_readiness_source_contract_preflight",
                return_value=self.source_ready,
            ),
            patch.object(
                command,
                "assert_runtime_dependency_preflight",
                return_value=_Dependency(),
            ),
            patch.object(
                command,
                "_capture_operational_git_provenance",
                return_value=self.provenance,
            ),
        ):
            report = command.build_activation_preflight(
                db_path=self.db, repository_root=ROOT
            )
        self.assertEqual(report["status"], "V2_9_8_OPERATIONAL_PREFLIGHT_READY")
        self.assertEqual(report["migration_count"], 45)
        self.assertEqual(report["canonical_migration_count"], 45)
        self.assertTrue(str(report["latest_migration"]).startswith("045"))
        self.assertEqual(report["source_calls"], 0)
        self.assertEqual(report["scheduler_runtime_calls"], 0)
        self.assertEqual(report["database_writes"], 0)
        self.assertEqual(report["integrity"], "ok")
        self.assertEqual(report["foreign_key_violations"], 0)
        self.assertFalse(any(report["active_counts"].values()))
        self.assertEqual(before, self.db.read_bytes())

    def test_preflight_reports_exact_migration_gate_on_mismatch(self) -> None:
        connection = sqlite3.connect(self.db)
        try:
            connection.execute(
                "DELETE FROM printer_schema_migrations WHERE version LIKE '045%'"
            )
            connection.commit()
        finally:
            connection.close()
        with (
            patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()),
            patch.object(
                command,
                "build_readiness_source_contract_preflight",
                return_value=self.source_ready,
            ),
            patch.object(
                command,
                "assert_runtime_dependency_preflight",
                return_value=_Dependency(),
            ),
            patch.object(
                command,
                "_capture_operational_git_provenance",
                return_value=self.provenance,
            ),
        ):
            with self.assertRaises(command.OperationalMemoryFactoryError) as raised:
                command.build_activation_preflight(
                    db_path=self.db, repository_root=ROOT
                )
        message = str(raised.exception)
        self.assertIn("gate=migration_ledger", message)
        self.assertIn("missing canonical migrations", message)
        self.assertIn("045_heartbeat_failure_evidence.sql", message)

    def test_status_and_report_only_are_zero_source_zero_write(self) -> None:
        before = self.db.read_bytes()
        with patch.object(command, "AUTHORITATIVE_DB", self.db.resolve()):
            status = command.operational_status()
            report = command.report_only()
        self.assertEqual(status["source_calls"], 0)
        self.assertEqual(status["scheduler_runtime_calls"], 0)
        self.assertEqual(status["database_writes"], 0)
        self.assertEqual(report["source_calls"], 0)
        self.assertEqual(report["scheduler_runtime_calls"], 0)
        self.assertEqual(report["database_writes"], 0)
        self.assertEqual(report["replay_new_source_calls"], 0)
        self.assertEqual(before, self.db.read_bytes())


class BackupRestoreAndCorpusShapeTests(unittest.TestCase):
    def test_backup_restore_preflight_passes_on_corpus_copy(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source.sqlite3"
            backup = root / "backup.sqlite3"
            restore = root / "restore.sqlite3"
            _copy_authoritative_corpus(source)
            _quiesce_operational_surfaces(source)
            identity = f"sha256:{command._sha256(source)}"
            result = operational_backup_restore_preflight(
                source,
                expected_source_path=source,
                expected_source_identity=identity,
                backup_path=backup,
                disposable_restore_root=root,
                restore_path=restore,
            )
            self.assertEqual(
                result["status"], "OPERATIONAL_BACKUP_RESTORE_PREFLIGHT_READY"
            )
            self.assertTrue(result["backup_byte_identical"])
            self.assertTrue(str(result["latest_rehearsed_migration"]).startswith("045"))
            self.assertEqual(result["sources_run"], False)
            self.assertEqual(result["scheduler_runtime_run"], False)

    def test_quiescent_corpus_copy_has_zero_fk_and_integrity_ok(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "corpus.sqlite3"
            _copy_authoritative_corpus(db)
            _quiesce_operational_surfaces(db)
            connection = sqlite3.connect(db)
            try:
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                fks = connection.execute("PRAGMA foreign_key_check").fetchall()
                migrations = [
                    str(row[0])
                    for row in connection.execute(
                        "SELECT version FROM printer_schema_migrations ORDER BY version"
                    )
                ]
            finally:
                connection.close()
            self.assertEqual(integrity, "ok")
            self.assertEqual(fks, [])
            self.assertEqual(migrations, list(canonical_migration_names()))


class HeartbeatCancellationRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db = self.root / "heartbeat.sqlite3"
        apply_migrations(self.db)
        create_campaign(
            self.db,
            campaign_id="campaign-19",
            configuration_id="configuration-19",
            configuration={"slots": 2},
            launch_provenance=_provenance(),
            db_mode=DB_MODE_PROOF_ISOLATED,
            db_target_identity="fixture-19",
            proof_source_db_identity="fixture-source-19",
            policy_version="v2-9.8b.19",
        )
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        create_campaign_run(
            self.connection,
            campaign_id="campaign-19",
            run_id="run-19",
            run_ordinal=1,
            now=NOW,
        )
        self.connection.execute(
            "UPDATE printer_memory_factory_campaigns SET campaign_state='RUNNING' "
            "WHERE campaign_id='campaign-19'"
        )
        self.connection.execute(
            "UPDATE printer_memory_factory_campaign_runs SET run_state='RUNNING' "
            "WHERE run_id='run-19'"
        )
        self.connection.commit()
        self.lock = self.root / "campaign.lease.lock"
        acquire_campaign_supervision(
            self.db,
            lock_path=self.lock,
            supervision_id="supervision-19",
            campaign_id="campaign-19",
            configuration_id="configuration-19",
            run_id="run-19",
            owner_id="owner-19",
            lease_seconds=90,
        )

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def test_successful_heartbeat_renewal(self) -> None:
        result = renew_campaign_lease(
            self.db,
            supervision_id="supervision-19",
            campaign_id="campaign-19",
            configuration_id="configuration-19",
            run_id="run-19",
            owner_id="owner-19",
            lease_seconds=90,
        )
        self.assertTrue(result.get("renewal_confirmed"))

    def test_sqlite_lock_failure_persists_safe_evidence(self) -> None:
        evidence = {
            "safe_error_type": "OperationalError",
            "safe_error_category": "SQLITE_LOCK_CONTENTION",
            "safe_message": "database is locked",
            "sqlite_locked": True,
            "attempted_at": NOW,
            "prior_heartbeat_at": NOW,
            "prior_lease_expires_at": NOW,
            "renewal_confirmed": False,
            "terminal_cause": "LEASE_RENEWAL_SQLITE_LOCKED",
        }
        persist_campaign_heartbeat_failure(
            self.db,
            supervision_id="supervision-19",
            campaign_id="campaign-19",
            configuration_id="configuration-19",
            run_id="run-19",
            owner_id="owner-19",
            evidence=evidence,
        )
        row = self.connection.execute(
            """
            SELECT terminal_cause, sqlite_locked, renewal_confirmed, safe_error_category
            FROM printer_memory_factory_campaign_heartbeat_failures
            WHERE run_id='run-19'
            """
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["terminal_cause"], "LEASE_RENEWAL_SQLITE_LOCKED")
        self.assertEqual(row["safe_error_category"], "SQLITE_LOCK_CONTENTION")
        self.assertEqual(int(row["sqlite_locked"]), 1)
        self.assertEqual(int(row["renewal_confirmed"]), 0)

    def test_cancellation_cleanup_leaves_zero_active_residue(self) -> None:
        cleanup = cleanup_campaign_supervision(
            self.db,
            supervision_id="supervision-19",
            campaign_id="campaign-19",
            configuration_id="configuration-19",
            run_id="run-19",
            owner_id="owner-19",
            terminal_status="FAILED",
            first_terminal_cause="OPERATOR_REQUESTED_COOPERATIVE_STOP",
        )
        self.assertTrue(cleanup.get("cleanup_completed"))
        self.assertTrue(cleanup.get("lease_released"))
        connection = sqlite3.connect(self.db)
        try:
            active_supervision = connection.execute(
                """
                SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision
                WHERE supervision_state IN ('ACTIVE', 'STOPPING')
                """
            ).fetchone()[0]
            active_runs = connection.execute(
                """
                SELECT COUNT(*) FROM printer_memory_factory_campaign_runs
                WHERE run_state IN ('RUNNING', 'STOP_REQUESTED')
                """
            ).fetchone()[0]
            locked_jobs = connection.execute(
                """
                SELECT COUNT(*) FROM printer_scheduler_jobs
                WHERE locked_at IS NOT NULL OR lock_owner IS NOT NULL
                """
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(active_supervision, 0)
        self.assertEqual(active_runs, 0)
        self.assertEqual(locked_jobs, 0)
        self.assertFalse(self.lock.exists() or self.lock.is_file())


class IdentityPropagationAndReplayTests(unittest.TestCase):
    def test_factory_campaign_report_identities_propagate_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "identity.sqlite3"
            reports = root / "reports"
            reports.mkdir()
            apply_migrations(db)
            campaign_id = "campaign-identity-19"
            configuration_id = "configuration-identity-19"
            run_id = "run-identity-19"
            cycle_id = "cycle-identity-19"
            report_id = "report-identity-19"
            factory_run_id = "factory-run-identity-19"
            create_campaign(
                db,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                configuration={
                    "token_capacity": 2,
                    "report_directory_identity": "identity-reports",
                },
                launch_provenance=_provenance(),
                db_mode=DB_MODE_OPERATIONAL_PERSISTENT,
                db_target_identity="identity-target",
                policy_version="v2-9.8b.19",
            )
            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                for token_id in (101, 102):
                    connection.execute(
                        "INSERT INTO printer_tokens(id,token_mint,token_status) "
                        "VALUES (?,?,?)",
                        (token_id, f"mint-{token_id}", "TRACK_NORMAL"),
                    )
                for pair_id, token_id in ((201, 101), (202, 102)):
                    connection.execute(
                        "INSERT INTO printer_pairs(id,token_id,pair_address,base_token_mint) "
                        "VALUES (?,?,?,?)",
                        (pair_id, token_id, f"pair-{pair_id}", f"mint-{token_id}"),
                    )
                for queue_id, token_id, pair_id in ((301, 101, 201), (302, 102, 202)):
                    connection.execute(
                        """
                        INSERT INTO printer_tracking_queue(
                            id,token_id,pair_id,tracking_lane,tracking_action,
                            priority_reason,queue_status,source_status,data_quality_label
                        ) VALUES (?,?,?,'TRACK_NORMAL','PROMOTE_TO_TRACK_NORMAL',
                                  'fixture','QUEUED','COMPLETE','CLEAN_DATA')
                        """,
                        (queue_id, token_id, pair_id),
                    )
                create_campaign_run(
                    connection,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    run_ordinal=1,
                    now=NOW,
                )
                create_cycle_with_two_slots(
                    connection,
                    campaign_id=campaign_id,
                    run_id=run_id,
                    cycle_id=cycle_id,
                    cycle_ordinal=1,
                    slots=(
                        {
                            "token_slot_id": "slot-1",
                            "slot_ordinal": 1,
                            "token_identity": "token-101",
                            "token_row_id": 101,
                            "mint_identity": "mint-101",
                            "pair_identity": "pair-201",
                            "pair_row_id": 201,
                            "lifecycle_identity": "life-1",
                            "tracking_queue_id": 301,
                        },
                        {
                            "token_slot_id": "slot-2",
                            "slot_ordinal": 2,
                            "token_identity": "token-102",
                            "token_row_id": 102,
                            "mint_identity": "mint-102",
                            "pair_identity": "pair-202",
                            "pair_row_id": 202,
                            "lifecycle_identity": "life-2",
                            "tracking_queue_id": 302,
                        },
                    ),
                    now=NOW,
                )
                connection.execute(
                    """
                    INSERT INTO printer_memory_factory_runs (
                        run_id, run_status, window_kind, db_mode, config_hash,
                        config_json, started_at
                    ) VALUES (?, 'SAFE_STOPPED', 'WINDOW_15M',
                              'OPERATIONAL_PERSISTENT', 'hash', '{}', ?)
                    """,
                    (factory_run_id, NOW),
                )
                connection.commit()
            finally:
                connection.close()

            reconciliation = reconcile_campaign_terminal(
                db,
                campaign_id=campaign_id,
                run_id=run_id,
                cycle_id=cycle_id,
                terminal_cause="SAFE_STOP_AFTER_WINDOW",
                run_status="SAFE_STOPPED",
                factory_run_id=factory_run_id,
                lifecycle_started=True,
                now=NOW,
            )
            self.assertFalse(reconciliation.get("restart_created"))
            self.assertFalse(reconciliation.get("successor_created"))
            reporting = assemble_campaign_terminal_reporting(
                db,
                run_id=run_id,
                cycle_id=cycle_id,
                terminal_cause="SAFE_STOP_AFTER_WINDOW",
                lifecycle={"run_id": factory_run_id, "run_status": "SAFE_STOPPED"},
                required_token_capacity=2,
            )
            payload = build_campaign_terminal_report(
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                run_id=run_id,
                cycle_id=cycle_id,
                report_id=report_id,
                factory_run_id=factory_run_id,
                execution_id="execution-identity-19",
                terminal_status="COMPLETED",
                terminal_cause="SAFE_STOP_AFTER_WINDOW",
                run_status="SAFE_STOPPED",
                lifecycle_started=True,
                reconciliation=reconciliation,
                forbidden_deltas={table: 0 for table in LOCKED_CAPABILITY_TABLES},
                launch_git_provenance=_provenance(),
                campaign_activity=reporting.get("campaign_activity"),
                blocked_supply=reporting.get("blocked_supply"),
                campaign_source_calls=0,
                campaign_scheduler_calls=0,
                candidates_observed=reporting.get("candidates_observed"),
                candidates_validated=reporting.get("candidates_validated"),
                eligible_candidates=reporting.get("eligible_candidates"),
                required_token_capacity=2,
                blocked_supply_reason=reporting.get("blocked_supply_reason"),
            )
            written = write_campaign_terminal_report(
                db,
                reports,
                report_id=report_id,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
                report=payload,
            )
            self.assertEqual(payload["identity"]["factory_run_id"], factory_run_id)
            self.assertEqual(payload["identity"]["campaign_id"], campaign_id)
            self.assertEqual(payload["identity"]["run_id"], run_id)
            self.assertEqual(written.get("report_id"), report_id)
            self.assertEqual(written.get("campaign_id"), campaign_id)
            replay = replay_campaign_terminal_report(
                db,
                reports,
                report_id=report_id,
                campaign_id=campaign_id,
                configuration_id=configuration_id,
            )
            self.assertEqual(replay.get("new_source_calls"), 0)
            self.assertEqual(replay.get("replay_new_source_calls"), 0)
            report_body = replay.get("report") or {}
            identity = report_body.get("identity") or {}
            self.assertEqual(identity.get("factory_run_id"), factory_run_id)
            self.assertEqual(identity.get("campaign_id"), campaign_id)
            self.assertEqual(identity.get("run_id"), run_id)
            self.assertEqual(identity.get("cycle_id"), cycle_id)
            self.assertEqual(identity.get("report_id"), report_id)


class PolicyLockSmokeTests(unittest.TestCase):
    def test_public_policy_ceilings_and_locks_unchanged(self) -> None:
        self.assertEqual(command.TOKEN_CAPACITY, 2)
        self.assertEqual(command.MAIN_WINDOW, "WINDOW_15M")
        self.assertEqual(command.ADMISSION_OPERATION_CEILING, 45)
        self.assertEqual(command.AUTOMATIC_RETRIES, 0)
        self.assertEqual(
            command.LOCKED_WINDOWS,
            ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"),
        )
        self.assertEqual(command.OPERATIONAL_GRADUATED_SUPPLY_KWARGS["front_door_max_candidates"], 6)
        self.assertEqual(command.OPERATIONAL_GRADUATED_SUPPLY_KWARGS["max_candidates"], 5)


class PowerShellWrapperContractTests(unittest.TestCase):
    def test_wrapper_invokes_public_operational_module_only(self) -> None:
        wrapper = (ROOT / "scripts" / "Start-PrinterV1-MemoryFactory.ps1").read_text(
            encoding="utf-8"
        )
        self.assertIn("printer_v1.operator_cli.operational_memory_factory_command", wrapper)
        self.assertIn("preflight-only", wrapper)
        self.assertIn("report-only", wrapper)
        self.assertNotIn("Start-V2-9-Proof", wrapper)
        self.assertNotIn("v2_9_7e_14_two_token_operational_pilot", wrapper)


if __name__ == "__main__":
    unittest.main()
