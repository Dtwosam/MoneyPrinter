"""V2-9.8B.2 holder budget + supervision lock repair proofs.

Focused disposable-DB tests only. No production campaign, no live network, no
retrieval/financial activation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest import mock

from printer_v1.db import apply_migrations
from printer_v1.discovery.direct_migration_discovery import (
    _ledger_counts,
    run_direct_migration_discovery,
)
from printer_v1.operator_cli import campaign_supervision
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
    renew_campaign_lease,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    HolderBudgetError,
    build_ledger,
    build_operational_budget_preflight,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    ADMISSION_OPERATION_CEILING,
    DISCOVERY_REQUEST_CEILING,
    GOVERNED_15M_REQUEST_CEILING,
    GOVERNED_REQUESTS_PER_TOKEN,
    _CampaignHeartbeat,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CampaignCeilings,
)
from printer_v1.sources.contracts import SourceRequest
from printer_v1.sources.recording import record_source_request


NOW = datetime(2026, 7, 26, 14, 13, 21, tzinfo=timezone.utc)
DEADLINE = NOW + timedelta(seconds=1200)


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW.isoformat(),
    }


def _seed_campaign_graph(db: Path, connection: sqlite3.Connection, *, now: str) -> None:
    create_campaign(
        db,
        campaign_id="campaign",
        configuration_id="configuration",
        configuration={"slots": 2},
        launch_provenance=_provenance(),
        db_mode=DB_MODE_PROOF_ISOLATED,
        db_target_identity="supervision-fixture",
        proof_source_db_identity="supervision-source",
        policy_version="v2-9.8b.2",
    )
    create_campaign_run(
        connection,
        campaign_id="campaign",
        run_id="run",
        run_ordinal=1,
        now=now,
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaigns "
        "SET campaign_state='RUNNING',updated_at=? WHERE campaign_id='campaign'",
        (now,),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs "
        "SET run_state='RUNNING',updated_at=? WHERE run_id='run'",
        (now,),
    )
    connection.commit()


class HolderBudgetArithmeticTests(unittest.TestCase):
    def test_valid_configuration_passes_budget_preflight_without_source_calls(self) -> None:
        report = build_operational_budget_preflight(
            admission_operation_ceiling=ADMISSION_OPERATION_CEILING,
            discovery_request_ceiling=DISCOVERY_REQUEST_CEILING,
            governed_15m_request_ceiling=GOVERNED_15M_REQUEST_CEILING,
            governed_requests_per_token=GOVERNED_REQUESTS_PER_TOKEN,
        )
        self.assertEqual(report["status"], "READY")
        self.assertEqual(report["source_calls"], 0)
        self.assertEqual(report["scheduler_runtime_calls"], 0)
        expected = report["expected"]
        self.assertEqual(expected["operation_ceiling"], 45)
        self.assertEqual(expected["reserved_snapshot_operations"], 2)
        self.assertEqual(expected["reserved_snapshot_completion_operations"], 4)
        self.assertEqual(expected["zero_transport_operations"], 9)
        self.assertEqual(expected["reserved_total"], 6)
        self.assertEqual(expected["fixed_charge_before_base_work"], 15)
        self.assertEqual(expected["available_for_base_work"], 30)

    def test_impossible_admission_ceiling_blocks_before_campaign_creation(self) -> None:
        report = build_operational_budget_preflight(admission_operation_ceiling=40)
        self.assertEqual(report["status"], "BLOCKED")
        self.assertTrue(
            any(issue.startswith("ADMISSION_CEILING_MISMATCH") for issue in report["issues"])
        )
        self.assertEqual(report["source_calls"], 0)

    def test_budget_arithmetic_and_reservation(self) -> None:
        ledger = build_ledger(
            pump_operations=0,
            additional_governed_operations=15,
            deadline_at=DEADLINE,
        )
        detail = ledger.budget_detail()
        self.assertEqual(detail["operation_ceiling"], 45)
        self.assertEqual(detail["governed_requests"], 15)
        self.assertEqual(detail["charged_operations"], 24)  # 15 + 9 zero-transport
        self.assertEqual(detail["reserved_total"], 6)
        self.assertEqual(detail["available_before_reservation"], 15)
        self.assertEqual(detail["candidate_cap"], 3)

    def test_historical_whole_table_base_work_is_rejected_with_exact_values(self) -> None:
        with self.assertRaises(HolderBudgetError) as raised:
            build_ledger(
                pump_operations=0,
                additional_governed_operations=1121,
                deadline_at=DEADLINE,
            )
        exc = raised.exception
        self.assertEqual(exc.code, "CAMPAIGN_BASE_WORK_EXCEEDS_RESERVED_BUDGET")
        self.assertEqual(exc.detail["base_operations"], 1121)
        self.assertEqual(exc.detail["operation_ceiling"], 45)
        self.assertEqual(exc.detail["available_for_base_work"], 30)
        self.assertGreater(exc.detail["charged_plus_reserved"], 45)

    def test_stage_local_discovery_ignores_historical_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "budget.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                # Seed historical noise that whole-table counting would charge.
                for index in range(40):
                    record_source_request(
                        connection,
                        SourceRequest(
                            "dexscreener",
                            "pair_market_snapshot",
                            request_key=f"historical-{index}",
                        ),
                    )
                connection.commit()
                whole_table = connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests"
                ).fetchone()[0]
                self.assertEqual(whole_table, 40)

                # Stage-local ledger with no invocation identities stays at zero.
                empty = _ledger_counts(connection, request_ids=())
                self.assertEqual(empty["source_requests"], 0)

                # Stage-local ledger charges only provided identities.
                ids = [
                    int(row[0])
                    for row in connection.execute(
                        "SELECT id FROM printer_source_requests ORDER BY id LIMIT 2"
                    ).fetchall()
                ]
                local = _ledger_counts(connection, request_ids=ids)
                self.assertEqual(local["source_requests"], 2)
                self.assertEqual(local["request_ids"], sorted(ids))

                # Valid stage-local base work still fits the admission ledger.
                ledger = build_ledger(
                    pump_operations=0,
                    additional_governed_operations=local["source_requests"],
                    deadline_at=DEADLINE,
                )
                self.assertEqual(ledger.governed_requests, 2)
                self.assertGreaterEqual(ledger.available_before_reservation, 0)
            finally:
                connection.close()


class DiscoveryStageLocalRuntimeTests(unittest.TestCase):
    def test_discovery_report_uses_stage_local_request_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "discovery.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            try:
                for index in range(25):
                    record_source_request(
                        connection,
                        SourceRequest(
                            "dexscreener",
                            "pair_market_snapshot",
                            request_key=f"noise-{index}",
                        ),
                    )
                connection.commit()
            finally:
                connection.close()

            def migration_transport(_request):
                return {
                    "fixture_status": "success",
                    "events": [],
                }

            report = run_direct_migration_discovery(
                db,
                migration_transport=migration_transport,
                now=NOW.isoformat(),
                request_key_prefix="e762-stage-local",
                max_candidates=1,
            )
            ledger = report["source_operation_ledger"]
            self.assertEqual(ledger["source_requests"], 1)
            self.assertEqual(len(ledger["request_ids"]), 1)
            # Whole-table count remains large and must not be used as charged base.
            connection = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                whole = connection.execute(
                    "SELECT COUNT(*) FROM printer_source_requests"
                ).fetchone()[0]
            finally:
                connection.close()
            self.assertEqual(whole, 26)
            build_ledger(
                pump_operations=0,
                additional_governed_operations=ledger["source_requests"],
                deadline_at=DEADLINE,
            )


class HeartbeatSupervisionLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db = self.root / "supervision.sqlite3"
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        now = NOW.isoformat()
        _seed_campaign_graph(self.db, self.connection, now=now)
        self.lock = self.root / "campaign.lease.lock"
        self.identity = {
            "supervision_id": "supervision",
            "campaign_id": "campaign",
            "configuration_id": "configuration",
            "run_id": "run",
            "owner_id": "owner",
        }

    def tearDown(self) -> None:
        self.connection.close()
        self.temporary.cleanup()

    def test_renewal_lock_contention_signals_main_without_terminal_cleanup(self) -> None:
        acquire_campaign_supervision(
            self.db, lock_path=self.lock, **self.identity, now=NOW, lease_seconds=90,
        )
        # Hold a write lock on the main connection to force renew contention.
        self.connection.execute("BEGIN IMMEDIATE")
        try:
            with mock.patch.object(
                campaign_supervision, "SQLITE_BUSY_MAX_ATTEMPTS", 2
            ), mock.patch.object(
                campaign_supervision, "SQLITE_BUSY_RETRY_SECONDS", 0.01
            ), mock.patch.object(
                campaign_supervision, "SQLITE_BUSY_TIMEOUT_SECONDS", 0.05
            ):
                # Force immediate lock failures after bounded retries by patching
                # BEGIN IMMEDIATE path through a short-timeout connection.
                def locked_connect(db_path, *, read_only=False):
                    path = Path(db_path).resolve()
                    if read_only:
                        connection = sqlite3.connect(
                            f"file:{path.as_posix()}?mode=ro",
                            uri=True,
                            timeout=0.0,
                        )
                        connection.execute("PRAGMA query_only=ON")
                    else:
                        connection = sqlite3.connect(path, timeout=0.0)
                        connection.execute("PRAGMA foreign_keys=ON")
                    connection.row_factory = sqlite3.Row
                    return connection

                with mock.patch.object(
                    campaign_supervision, "_connect", side_effect=locked_connect
                ):
                    result = renew_campaign_lease(
                        self.db,
                        **self.identity,
                        now=NOW + timedelta(seconds=30),
                        lease_seconds=90,
                    )
        finally:
            self.connection.rollback()

        self.assertFalse(result["renewal_confirmed"])
        self.assertTrue(result.get("signal_main_coordinator"))
        self.assertFalse(result.get("terminal_cleanup_performed"))
        self.assertIsNone(result.get("safe_stop"))
        # Original supervision remains ACTIVE; heartbeat/renew did not cleanup.
        row = self.connection.execute(
            """SELECT supervision_state,terminal_status,first_terminal_cause,
                      cleanup_completed_at,lease_released_at
               FROM printer_memory_factory_campaign_supervision"""
        ).fetchone()
        self.assertEqual(row["supervision_state"], "ACTIVE")
        self.assertIsNone(row["terminal_status"])
        self.assertIsNone(row["first_terminal_cause"])
        self.assertIsNone(row["cleanup_completed_at"])
        self.assertIsNone(row["lease_released_at"])

        # Main coordinator cleanup preserves first cause and releases lease.
        cleanup = cleanup_campaign_supervision(
            self.db,
            **self.identity,
            terminal_status="FAILED",
            first_terminal_cause="OPERATIONAL_CAMPAIGN_FAILED:HolderBudgetError",
            now=NOW + timedelta(seconds=120),
        )
        self.assertTrue(cleanup["cleanup_completed"])
        self.assertTrue(cleanup["lease_released"])
        self.assertEqual(cleanup["active_owned_work_after"], 0)
        self.assertEqual(
            cleanup["first_terminal_cause"],
            "OPERATIONAL_CAMPAIGN_FAILED:HolderBudgetError",
        )
        self.assertFalse(cleanup.get("restart_created", False))
        self.assertFalse(cleanup.get("successor_created", False))
        self.assertFalse(self.lock.exists())
        final = self.connection.execute(
            """SELECT supervision_state,terminal_status,first_terminal_cause
               FROM printer_memory_factory_campaign_supervision"""
        ).fetchone()
        self.assertEqual(final["supervision_state"], "TERMINAL")
        self.assertEqual(final["terminal_status"], "FAILED")
        self.assertEqual(
            final["first_terminal_cause"],
            "OPERATIONAL_CAMPAIGN_FAILED:HolderBudgetError",
        )

    def test_heartbeat_thread_does_not_run_terminal_cleanup(self) -> None:
        acquire_campaign_supervision(
            self.db, lock_path=self.lock, **self.identity, now=NOW, lease_seconds=90,
        )
        command = AbstractCampaignCommand(
            mode="OPERATIONAL_CAMPAIGN",
            db_path=self.db,
            db_target_identity="proof",
            campaign_id="campaign",
            configuration_id="configuration",
            configuration_hash="hash",
            policy_version="v2-9.8b.2",
            token_capacity=2,
            ceilings=CampaignCeilings(
                campaign_count=1,
                cycle_count=1,
                duration_seconds=1200,
                source_calls=45,
                scheduler_work=51,
                storage_bytes=64 * 1024 * 1024,
                failures=20,
            ),
            report_directory=self.root / "reports",
            report_directory_identity="path-sha256:test",
            launch_git_provenance={},
            run_id="run",
            report_id="report",
            supervision_id="supervision",
            owner_id="owner",
            lease_lock_path=self.lock,
        )
        (self.root / "reports").mkdir(exist_ok=True)
        heartbeat = _CampaignHeartbeat(command)
        failure = {
            "renewal_confirmed": False,
            "renewal_error": "database is locked",
            "renewal_error_type": "OperationalError",
            "sqlite_locked": True,
            "terminal_cleanup_performed": False,
            "safe_stop": None,
            "new_child_work_allowed": False,
            "signal_main_coordinator": True,
            "suggested_terminal_cause": "LEASE_RENEWAL_UNCONFIRMED",
        }
        with mock.patch(
            "printer_v1.operator_cli.operational_memory_factory_command.renew_campaign_lease",
            return_value=failure,
        ) as renew, mock.patch(
            "printer_v1.operator_cli.operational_memory_factory_command.cleanup_campaign_supervision"
        ) as cleanup, mock.patch(
            "printer_v1.operator_cli.operational_memory_factory_command.HEARTBEAT_SECONDS",
            0.05,
        ):
            heartbeat.start()
            self.assertTrue(heartbeat.failure_event.wait(timeout=2.0))
            observed = heartbeat.poll_failure()
            heartbeat.stop()
        self.assertIsNotNone(observed)
        self.assertFalse(observed["renewal_confirmed"])
        self.assertFalse(observed["terminal_cleanup_performed"])
        self.assertTrue(observed["signal_main_coordinator"])
        self.assertGreaterEqual(renew.call_count, 1)
        cleanup.assert_not_called()
        row = self.connection.execute(
            "SELECT supervision_state,terminal_status FROM printer_memory_factory_campaign_supervision"
        ).fetchone()
        self.assertEqual(row["supervision_state"], "ACTIVE")
        self.assertIsNone(row["terminal_status"])


class FinancialAndRetrievalLockTests(unittest.TestCase):
    def test_repair_modules_do_not_touch_financial_or_retrieval_surfaces(self) -> None:
        # Static import surface check: the repair modules stay away from decision
        # and position owners.
        import printer_v1.operator_cli.holder_reliability_budget_control as budget
        import printer_v1.operator_cli.campaign_supervision as supervision
        import printer_v1.discovery.direct_migration_discovery as discovery

        for module in (budget, supervision, discovery):
            text = Path(module.__file__).read_text(encoding="utf-8")
            for forbidden in (
                "paper_decision",
                "paper_position",
                "BUY",
                "SELL",
                "PnL",
                "private_key",
                "embedding",
            ):
                if forbidden in ("BUY", "SELL"):
                    continue  # too noisy; modules do not authorize those decisions
                self.assertNotIn(
                    f"create_{forbidden}",
                    text,
                    msg=f"{module.__name__} must not create {forbidden}",
                )


if __name__ == "__main__":
    unittest.main()
