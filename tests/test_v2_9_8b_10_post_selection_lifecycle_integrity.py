"""V2-9.8B.10 post-selection lifecycle integrity repair focused proofs.

Disposable DBs and injected fixtures only. No production campaign, no live
network, no retrieval/financial activation.
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
from printer_v1.db.migrate import (
    canonical_migration_count,
    canonical_migration_names,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    AbstractCampaignCommand,
    CampaignCeilings,
)
from printer_v1.operator_cli.campaign_ownership import create_campaign_run
from printer_v1.operator_cli.campaign_persistence import (
    DB_MODE_OPERATIONAL_PERSISTENT,
    DB_MODE_PROOF_ISOLATED,
    create_campaign,
)
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    cleanup_campaign_supervision,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    OPERATION_CEILING,
    persist_ledger,
    build_ledger,
)
from printer_v1.operator_cli.one_command_15m_factory import run_one_command_15m_factory
from printer_v1.operator_cli.operational_memory_factory_command import (
    EXPECTED_MIGRATION_COUNT,
    OperationalMemoryFactoryError,
    _latest_campaign_source_total,
    _terminalize_initialized_failure,
    _with_sqlite_busy_retry,
    main,
)
from printer_v1.operator_cli.pilot_input_readiness import (
    ReadinessCandidate,
    build_pilot_input_ready_bundle,
)


NOW = datetime(2026, 7, 27, 0, 15, 20, tzinfo=timezone.utc)
NOW_ISO = NOW.isoformat()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "f" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": NOW_ISO,
    }


def _seed_running_campaign(
    db: Path,
    connection: sqlite3.Connection,
    *,
    campaign_id: str = "campaign-10",
    run_id: str = "run-10",
    cycle_id: str = "cycle-10",
    configuration_id: str = "configuration-10",
    db_mode: str = DB_MODE_OPERATIONAL_PERSISTENT,
) -> str:
    create_campaign(
        db,
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        configuration={"slots": 2},
        launch_provenance=_provenance(),
        db_mode=db_mode,
        db_target_identity="fixture-db",
        proof_source_db_identity=(
            "proof-source" if db_mode == DB_MODE_PROOF_ISOLATED else None
        ),
        policy_version="v2-9.8b.10",
    )
    create_campaign_run(
        connection,
        campaign_id=campaign_id,
        run_id=run_id,
        run_ordinal=1,
        now=NOW_ISO,
    )
    connection.execute(
        """INSERT INTO printer_memory_factory_campaign_cycles(
               cycle_id,campaign_id,run_id,cycle_ordinal,cycle_state,
               created_at,updated_at
           ) VALUES (?,?,?,1,'PLANNED',?,?)""",
        (cycle_id, campaign_id, run_id, NOW_ISO, NOW_ISO),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaigns "
        "SET campaign_state='RUNNING',updated_at=? WHERE campaign_id=?",
        (NOW_ISO, campaign_id),
    )
    connection.execute(
        "UPDATE printer_memory_factory_campaign_runs "
        "SET run_state='RUNNING',updated_at=? WHERE run_id=?",
        (NOW_ISO, run_id),
    )
    connection.commit()
    return cycle_id


def _command(
    db: Path,
    *,
    campaign_id: str,
    run_id: str,
    configuration_id: str,
    supervision_id: str,
    owner_id: str,
    lock_path: Path,
    report_id: str = "report-10",
) -> AbstractCampaignCommand:
    return AbstractCampaignCommand(
        mode="OPERATIONAL",
        db_path=db,
        db_target_identity="fixture-db",
        campaign_id=campaign_id,
        configuration_id=configuration_id,
        configuration_hash="h" * 40,
        policy_version="v2-9.8b.10",
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
        report_directory=db.parent / "reports",
        report_directory_identity="reports",
        launch_git_provenance=_provenance(),
        run_id=run_id,
        report_id=report_id,
        supervision_id=supervision_id,
        owner_id=owner_id,
        lease_lock_path=lock_path,
    )


class MigrationAndFactoryInsertTests(unittest.TestCase):
    def test_migration_count_and_operational_factory_insert(self) -> None:
        expected_count = canonical_migration_count()
        expected_names = canonical_migration_names()
        self.assertEqual(EXPECTED_MIGRATION_COUNT, expected_count)
        self.assertEqual(expected_count, len(expected_names))
        self.assertEqual(expected_names[-1], "049_candidate_acquisition_integration.sql")
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "mig.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            try:
                count = connection.execute(
                    "SELECT COUNT(*) FROM printer_schema_migrations"
                ).fetchone()[0]
                self.assertEqual(count, expected_count)
                latest = connection.execute(
                    "SELECT version FROM printer_schema_migrations "
                    "ORDER BY version DESC LIMIT 1"
                ).fetchone()
                self.assertIsNotNone(latest)
                self.assertEqual(latest[0], expected_names[-1])
                connection.execute(
                    """INSERT INTO printer_memory_factory_runs
                       (run_id,run_status,window_kind,db_mode,config_hash,
                        config_json,started_at)
                       VALUES ('op-run','RUNNING','WINDOW_15M',
                               'OPERATIONAL_PERSISTENT','hash','{}',?)""",
                    (NOW_ISO,),
                )
                connection.execute(
                    """INSERT INTO printer_memory_factory_runs
                       (run_id,run_status,window_kind,db_mode,config_hash,
                        config_json,started_at)
                       VALUES ('proof-run','RUNNING','WINDOW_15M',
                               'PROOF_ONLY','hash','{}',?)""",
                    (NOW_ISO,),
                )
                connection.commit()
                modes = {
                    row[0]
                    for row in connection.execute(
                        "SELECT db_mode FROM printer_memory_factory_runs"
                    )
                }
                self.assertEqual(modes, {"OPERATIONAL_PERSISTENT", "PROOF_ONLY"})
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        """INSERT INTO printer_memory_factory_runs
                           (run_id,run_status,window_kind,db_mode,config_hash,
                            config_json,started_at)
                           VALUES ('bad','RUNNING','WINDOW_15M',
                                   'PROOF_ISOLATED','hash','{}',?)""",
                        (NOW_ISO,),
                    )
            finally:
                connection.close()

    def test_factory_insert_sql_accepts_operational_mode_exactly_once(self) -> None:
        """Exact lifecycle-entry INSERT that failed in production now succeeds."""
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "factory.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            try:
                connection.execute(
                    "INSERT INTO printer_memory_factory_runs "
                    "(run_id,run_status,window_kind,db_mode,config_hash,"
                    "config_json,started_at,created_at,updated_at) "
                    "VALUES (?,'RUNNING',?,?,?,?,?,?,?)",
                    (
                        "lifecycle-entry-run",
                        "WINDOW_15M",
                        "OPERATIONAL_PERSISTENT",
                        "hash",
                        "{}",
                        NOW_ISO,
                        NOW_ISO,
                        NOW_ISO,
                    ),
                )
                connection.commit()
                rows = connection.execute(
                    "SELECT run_id, db_mode FROM printer_memory_factory_runs"
                ).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][1], "OPERATIONAL_PERSISTENT")
                # Duplicate run_id fails closed (unique) without partial second graph.
                with self.assertRaises(sqlite3.IntegrityError):
                    connection.execute(
                        "INSERT INTO printer_memory_factory_runs "
                        "(run_id,run_status,window_kind,db_mode,config_hash,"
                        "config_json,started_at) VALUES "
                        "(?,'RUNNING','WINDOW_15M','OPERATIONAL_PERSISTENT',"
                        "'hash','{}',?)",
                        ("lifecycle-entry-run", NOW_ISO),
                    )
            finally:
                connection.close()

    def test_proof_mode_factory_still_inserts_proof_only(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "proof.sqlite3"
            backup = root / "backup.sqlite3"
            apply_migrations(db)
            backup.write_bytes(db.read_bytes())

            def discovery_runner(_args):
                return {
                    "selection_handoff_report": {
                        "batch_id": "origin-activated:cycle-empty",
                        "selection_seed": "seed-10",
                        "eligible_pool_size": 0,
                    },
                    "discovery_results": [],
                }

            report = run_one_command_15m_factory(
                db,
                backup,
                operator_approved=True,
                proof_mode=True,
                operational_persistent_mode=False,
                discovery_runner=discovery_runner,
                max_selected_tokens=2,
                total_duration_seconds=1200.0,
                launch_provenance=_provenance(),
            )
            self.assertIsInstance(report, dict)
            connection = sqlite3.connect(db)
            try:
                rows = connection.execute(
                    "SELECT db_mode FROM printer_memory_factory_runs"
                ).fetchall()
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0][0], "PROOF_ONLY")
            finally:
                connection.close()


class ReadinessAndHandoffIdentityTests(unittest.TestCase):
    def test_two_token_readiness_bundle_is_immutable_and_distinct(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "ready.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            try:
                latest = ReadinessCandidate(
                    mint="UUdfUfhkqWEQK9wqADgQTQSbE4qpNkNaeCZdjPPpump",
                    pool="7PZL3Fo1bHSkKiSymZsRHjhX4swn1n9WHvupQ4qQcnFR",
                    market_identity=(
                        "solana-mainnet:pumpswap:"
                        "7PZL3Fo1bHSkKiSymZsRHjhX4swn1n9WHvupQ4qQcnFR"
                    ),
                    liquidity_usd=12000.0,
                    liquidity_observed_at=NOW_ISO,
                    activation_route="GRADUATION_NATIVE",
                    holder_eligible=True,
                    provenance="LATEST_GRADUATED",
                )
                persisted = ReadinessCandidate(
                    mint="7tKKxaDcb7w1J9aLz5mFkSypxJjQKHaDfAEYZZxGpump",
                    pool="GocsVH4qcQfPsHqgCDiZPWRmq1Q1FBZn2Qv7BVKbgEix",
                    market_identity=(
                        "solana-mainnet:pumpswap:"
                        "GocsVH4qcQfPsHqgCDiZPWRmq1Q1FBZn2Qv7BVKbgEix"
                    ),
                    liquidity_usd=9000.0,
                    liquidity_observed_at=NOW_ISO,
                    activation_route="GRADUATION_NATIVE",
                    holder_eligible=True,
                    provenance="LATEST_GRADUATED",
                )
                bundle = build_pilot_input_ready_bundle(
                    connection,
                    readiness_id="run-10:cycle-10:pilot-input",
                    latest=latest,
                    persisted=persisted,
                    holder_evidence={
                        latest.mint.lower(): {"eligible": True},
                        persisted.mint.lower(): {"eligible": True},
                    },
                    source_ledger={
                        "operation_ceiling": 45,
                        "governed_requests": 18,
                        "underlying_transport_operations": 19,
                        "zero_transport_operations": 9,
                    },
                    selection_seed="seed-10",
                    git_provenance_identity="f" * 40,
                    configuration_hash="c" * 40,
                    expires_at=(NOW + timedelta(minutes=10)).isoformat(),
                    now=NOW_ISO,
                )
                self.assertEqual(bundle["readiness_id"], "run-10:cycle-10:pilot-input")
                self.assertNotEqual(
                    bundle["latest"]["mint"], bundle["persisted"]["mint"]
                )
                # Conflicting rewrite fails closed.
                with self.assertRaises(Exception):
                    build_pilot_input_ready_bundle(
                        connection,
                        readiness_id="run-10:cycle-10:pilot-input",
                        latest=persisted,
                        persisted=latest,
                        holder_evidence={},
                        source_ledger={"operation_ceiling": 45, "governed_requests": 1},
                        selection_seed="other",
                        git_provenance_identity="f" * 40,
                        configuration_hash="c" * 40,
                        expires_at=(NOW + timedelta(minutes=10)).isoformat(),
                        now=NOW_ISO,
                    )
            finally:
                connection.close()


class TerminalizationAndHeartbeatTests(unittest.TestCase):
    def test_post_selection_exception_terminalizes_and_releases_lease(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            db = root / "term.sqlite3"
            reports = root / "reports"
            reports.mkdir()
            apply_migrations(db)
            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                cycle_id = _seed_running_campaign(db, connection)
                ledger = build_ledger(
                    pump_operations=0,
                    additional_governed_operations=18,
                    deadline_at=NOW + timedelta(seconds=1200),
                )
                persist_ledger(
                    connection,
                    run_id="run-10",
                    cycle_id=str(cycle_id),
                    ledger=ledger,
                    now=NOW_ISO,
                )
                connection.commit()
            finally:
                connection.close()

            lock_path = root / "campaign.lease.lock"
            acquire_campaign_supervision(
                db,
                lock_path=lock_path,
                supervision_id="supervision-10",
                campaign_id="campaign-10",
                configuration_id="configuration-10",
                run_id="run-10",
                owner_id="owner-10",
                lease_seconds=90,
            )
            command = _command(
                db,
                campaign_id="campaign-10",
                run_id="run-10",
                configuration_id="configuration-10",
                supervision_id="supervision-10",
                owner_id="owner-10",
                lock_path=lock_path,
            )
            paths = {
                "reports": reports,
                "summary": root / "terminal-summary.json",
            }
            original = sqlite3.IntegrityError(
                "CHECK constraint failed: db_mode = 'PROOF_ONLY'"
            )
            terminal = _terminalize_initialized_failure(
                original_exception=original,
                command=command,
                cycle_id=str(cycle_id),
                execution_id="execution-10",
                paths=paths,
                launch_git_provenance=_provenance(),
            )
            self.assertEqual(
                terminal["first_terminal_cause"],
                "OPERATIONAL_CAMPAIGN_FAILED:IntegrityError",
            )
            self.assertTrue(terminal["cleanup"].get("cleanup_completed"))
            self.assertTrue(terminal["cleanup"].get("lease_released"))
            self.assertFalse(terminal["restart_created"])
            self.assertFalse(terminal["successor_created"])
            self.assertEqual(terminal.get("campaign_source_calls"), 18)

            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            try:
                campaign = connection.execute(
                    "SELECT campaign_state, first_terminal_cause "
                    "FROM printer_memory_factory_campaigns WHERE campaign_id=?",
                    ("campaign-10",),
                ).fetchone()
                run = connection.execute(
                    "SELECT run_state, first_terminal_cause "
                    "FROM printer_memory_factory_campaign_runs WHERE run_id=?",
                    ("run-10",),
                ).fetchone()
                cycle = connection.execute(
                    "SELECT cycle_state, first_terminal_cause "
                    "FROM printer_memory_factory_campaign_cycles WHERE cycle_id=?",
                    (cycle_id,),
                ).fetchone()
                supervision = connection.execute(
                    "SELECT supervision_state, terminal_status, lease_released_at "
                    "FROM printer_memory_factory_campaign_supervision "
                    "WHERE supervision_id=?",
                    ("supervision-10",),
                ).fetchone()
                self.assertEqual(campaign["campaign_state"], "TERMINAL_FAILED")
                self.assertEqual(run["run_state"], "TERMINAL_FAILED")
                self.assertEqual(cycle["cycle_state"], "TERMINAL_FAILED")
                self.assertEqual(
                    campaign["first_terminal_cause"],
                    "OPERATIONAL_CAMPAIGN_FAILED:IntegrityError",
                )
                self.assertEqual(supervision["supervision_state"], "TERMINAL")
                self.assertIsNotNone(supervision["lease_released_at"])
                # First cause immutable on second cleanup.
                cleanup_again = cleanup_campaign_supervision(
                    db,
                    supervision_id="supervision-10",
                    campaign_id="campaign-10",
                    configuration_id="configuration-10",
                    run_id="run-10",
                    owner_id="owner-10",
                    terminal_status="COMPLETED",
                    first_terminal_cause="SHOULD_NOT_REPLACE",
                )
                self.assertTrue(cleanup_again.get("idempotent_replay"))
                self.assertEqual(
                    cleanup_again["first_terminal_cause"],
                    "OPERATIONAL_CAMPAIGN_FAILED:IntegrityError",
                )
            finally:
                connection.close()

    def test_busy_retry_survives_transient_database_locked(self) -> None:
        calls = {"n": 0}

        def flaky() -> str:
            calls["n"] += 1
            if calls["n"] < 3:
                raise sqlite3.OperationalError("database is locked")
            return "ok"

        self.assertEqual(_with_sqlite_busy_retry("flaky", flaky, attempts=5), "ok")
        self.assertEqual(calls["n"], 3)

    def test_busy_retry_gives_up_on_non_lock_errors(self) -> None:
        def permanent() -> None:
            raise sqlite3.OperationalError("no such table: missing")

        with self.assertRaises(sqlite3.OperationalError):
            _with_sqlite_busy_retry("permanent", permanent, attempts=3)


class PublicFailureSurfaceTests(unittest.TestCase):
    def test_latest_campaign_source_total_reads_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            db = Path(temporary) / "src.sqlite3"
            apply_migrations(db)
            connection = sqlite3.connect(db)
            connection.row_factory = sqlite3.Row
            try:
                cycle_id = _seed_running_campaign(
                    db, connection, db_mode=DB_MODE_OPERATIONAL_PERSISTENT
                )
                # Minimal supervision row for join.
                connection.execute(
                    """INSERT INTO printer_memory_factory_campaign_supervision(
                           supervision_id,campaign_id,configuration_id,run_id,owner_id,
                           supervision_state,terminal_status,first_terminal_cause,
                           heartbeat_at,lease_expires_at,lease_lock_path,
                           cleanup_completed_at,created_at,updated_at
                       ) VALUES (?,?,?,?,?,'TERMINAL','FAILED',?,?,?,?,?,?,?)""",
                    (
                        "supervision-10",
                        "campaign-10",
                        "configuration-10",
                        "run-10",
                        "owner-10",
                        "OPERATIONAL_CAMPAIGN_FAILED:IntegrityError",
                        NOW_ISO,
                        NOW_ISO,
                        str(Path(temporary) / "lock"),
                        NOW_ISO,
                        NOW_ISO,
                        NOW_ISO,
                    ),
                )
                ledger = build_ledger(
                    pump_operations=0,
                    additional_governed_operations=18,
                    deadline_at=NOW + timedelta(seconds=1200),
                )
                persist_ledger(
                    connection,
                    run_id="run-10",
                    cycle_id=str(cycle_id),
                    ledger=ledger,
                    now=NOW_ISO,
                )
                connection.commit()
            finally:
                connection.close()
            total = _latest_campaign_source_total(db)
            self.assertEqual(total, 18)

    def test_main_exception_surface_reports_durable_source_total(self) -> None:
        from printer_v1.operator_cli import operational_memory_factory_command as omf

        def _failing_run(**_kwargs):
            omf._ACTION_RUN_CONTEXT["run_id"] = "run-with-ledger"
            raise sqlite3.IntegrityError(
                "CHECK constraint failed: db_mode = 'PROOF_ONLY'"
            )

        with mock.patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "run_operational_campaign",
            side_effect=_failing_run,
        ), mock.patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "_latest_campaign_source_total",
            return_value=18,
        ) as source_total:
            code = main(["run", "--operator-approved"])
        self.assertEqual(code, 1)
        source_total.assert_called_once()
        self.assertEqual(source_total.call_args.kwargs.get("run_id"), "run-with-ledger")

    def test_main_blocked_preflight_does_not_inherit_prior_campaign_source_total(
        self,
    ) -> None:
        with mock.patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "build_activation_preflight",
            side_effect=OperationalMemoryFactoryError(
                "operational preflight blocked: gate=migration_ledger: test"
            ),
        ), mock.patch(
            "printer_v1.operator_cli.operational_memory_factory_command."
            "_latest_campaign_source_total",
            return_value=22,
        ) as source_total:
            code = main(["preflight-only"])
        self.assertEqual(code, 1)
        source_total.assert_not_called()


class LockPreservationSmokeTests(unittest.TestCase):
    def test_no_restart_successor_or_ceiling_drift_constants(self) -> None:
        self.assertEqual(OPERATION_CEILING, 45)
        self.assertEqual(EXPECTED_MIGRATION_COUNT, canonical_migration_count())
        self.assertGreaterEqual(EXPECTED_MIGRATION_COUNT, 45)


if __name__ == "__main__":
    unittest.main()
