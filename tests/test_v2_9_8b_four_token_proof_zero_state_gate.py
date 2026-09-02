"""Focused contract for the read-only four-token proof pre-consumption gate.

Offline only. Every database in this file is a disposable temporary fixture.
The gate under test must be strictly read-only: it creates no campaign,
reservation, lease, discovery attempt, Scheduler job, or source request, starts
no Printer process, and never touches the authoritative database.
"""

from __future__ import annotations

from datetime import datetime, timezone
import sqlite3
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import (
    four_token_proof_one_shot_wrapper as four_token,
)
from printer_v1.operator_cli import four_token_proof_zero_state_gate as gate
from printer_v1.operator_cli.pre_authorization_migration_ledger_guard import (
    PACKAGE_BINDING_FIELDS,
    inspect_authoritative_database,
)


NOW = datetime(2026, 8, 13, 22, 0, tzinfo=timezone.utc)

ENVIRONMENT = {
    "PRINTER_SOLANA_RPC_URL": "https://api.mainnet-beta.solana.com",
    "PRINTER_DEXSCREENER_BASE_URL": "https://api.dexscreener.com",
}


def _database_binding(db_path):
    identity = inspect_authoritative_database(db_path)
    return {field: identity[field] for field in PACKAGE_BINDING_FIELDS}


def _document(db_path):
    return four_token.fixture_authorization_document(
        branch="agent/test-branch",
        head="a" * 40,
        database=_database_binding(db_path),
    )


def _quiescent_database(tmp_path):
    path = tmp_path / "four-token-zero-state.sqlite3"
    apply_migrations(path)
    return path


def _campaign_supervision_row(
    connection,
    *,
    supervision_state,
    supervision_id="supervision-1",
    campaign_state="TERMINAL_COMPLETED",
    run_state="TERMINAL_COMPLETED",
):
    """Insert one durable campaign-supervision row with its exact parents."""
    stamp = NOW.isoformat()
    cause = "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED"
    campaign_terminal = campaign_state.startswith("TERMINAL_")
    run_terminal = run_state.startswith("TERMINAL_")
    connection.execute(
        "INSERT INTO printer_memory_factory_campaigns("
        "campaign_id,campaign_state,db_mode,db_target_identity,policy_version,"
        "first_terminal_cause,terminal_at,created_at,updated_at) "
        "VALUES (?,?,'OPERATIONAL_PERSISTENT','db-1','p-1',?,?,?,?)",
        (
            f"campaign-{supervision_id}",
            campaign_state,
            cause if campaign_terminal else None,
            stamp if campaign_terminal else None,
            stamp,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_configurations("
        "configuration_id,campaign_id,configuration_hash,configuration_json,"
        "launch_provenance_json,created_at) VALUES (?,?,?,'{}','{}',?)",
        (
            f"configuration-{supervision_id}",
            f"campaign-{supervision_id}",
            "a" * 64,
            stamp,
        ),
    )
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_runs("
        "run_id,campaign_id,run_ordinal,run_state,first_terminal_cause,"
        "terminal_at,created_at,updated_at) VALUES (?,?,1,?,?,?,?,?)",
        (
            f"run-{supervision_id}",
            f"campaign-{supervision_id}",
            run_state,
            cause if run_terminal else None,
            stamp if run_terminal else None,
            stamp,
            stamp,
        ),
    )
    terminal = supervision_state == "TERMINAL"
    connection.execute(
        "INSERT INTO printer_memory_factory_campaign_supervision("
        "supervision_id,campaign_id,configuration_id,run_id,owner_id,"
        "supervision_state,terminal_status,first_terminal_cause,heartbeat_at,"
        "lease_expires_at,lease_lock_path,cleanup_completed_at,created_at,"
        "updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            supervision_id,
            f"campaign-{supervision_id}",
            f"configuration-{supervision_id}",
            f"run-{supervision_id}",
            "owner-1",
            supervision_state,
            "COMPLETED" if terminal else None,
            "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED" if terminal else None,
            stamp,
            stamp,
            "/tmp/campaign.lease.lock",
            stamp if terminal else None,
            stamp,
            stamp,
        ),
    )


def _proof_supervision_row(
    connection, *, execution_status, execution_id="execution-1", process_id=None
):
    """Insert one durable proof-supervision row."""
    stamp = NOW.isoformat()
    terminal = execution_status == "TERMINAL"
    connection.execute(
        "INSERT INTO printer_proof_run_supervision("
        "execution_id,proof_scope,owner_launcher_type,process_id,"
        "execution_status,terminal_status,first_stop_reason,heartbeat_at,"
        "lease_expires_at,proof_db_path,backup_db_path,one_proof_lock_path,"
        "stdout_log_path,stderr_log_path,started_at,finished_at,created_at,"
        "updated_at) VALUES (?,'V2_9','TEST_FIXTURE',?,?,?,?,?,?,"
        "'/tmp/proof.sqlite3','/tmp/backup.sqlite3','/tmp/one.lock',"
        "'/tmp/out.log','/tmp/err.log',?,?,?,?)",
        (
            execution_id,
            process_id,
            execution_status,
            "COMPLETED" if terminal else None,
            "PROOF_COMPLETE" if terminal else None,
            stamp,
            stamp,
            stamp,
            stamp if terminal else None,
            stamp,
            stamp,
        ),
    )


class FourTokenProofZeroStateGateTests(unittest.TestCase):
    def setUp(self) -> None:
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _assert_ready(self, path, **overrides):
        arguments = {
            "db_path": path,
            "authorization_document": _document(path),
            "environment": dict(ENVIRONMENT),
            "printer_process_probe": lambda: (),
            "migrations_dir": None,
        }
        arguments.update(overrides)
        return gate.assert_four_token_proof_zero_state(**arguments)

    def test_quiescent_current_head_database_passes_read_only(self) -> None:
        path = _quiescent_database(self.tmp_path)
        before = path.stat()
        evidence = self._assert_ready(path)
        after = path.stat()
        self.assertEqual(
            evidence["schema_version"], gate.ZERO_STATE_SCHEMA_VERSION
        )
        self.assertIs(evidence["zero_state_ready"], True)
        self.assertEqual(evidence["blockers"], [])
        self.assertEqual(evidence["migration_count"], 59)
        self.assertEqual(
            evidence["migration_head"],
            "059_pair_ready_parent_terminal_cancellation_transition.sql",
        )
        self.assertEqual(evidence["integrity_check"], "ok")
        self.assertEqual(evidence["foreign_key_violations"], 0)
        self.assertEqual(evidence["printer_processes"], 0)
        self.assertEqual(evidence["sidecars"], [])
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        self.assertEqual(after.st_size, before.st_size)

    def test_required_zero_state_domains_are_all_projected(self) -> None:
        path = _quiescent_database(self.tmp_path)
        connection = sqlite3.connect(path)
        try:
            projection = gate.project_four_token_proof_zero_state(connection)
        finally:
            connection.close()
        self.assertEqual(
            set(projection), set(gate.REQUIRED_ZERO_STATE_DOMAINS)
        )
        self.assertTrue(
            all(int(value) == 0 for value in projection.values()), projection
        )
        for domain in (
            "active_campaigns",
            "active_campaign_runs",
            "active_campaign_cycles",
            "active_campaign_scheduler_work",
            "campaign_supervision",
            "active_discovery_work",
            "active_factory_runs",
            "active_factory_steps",
            "pre_admission_discovery_attempts",
            "active_pre_lifecycle_discovery_refresh_work",
            "active_pre_lifecycle_discovery_refresh_waits",
            "active_scheduler_jobs",
        ):
            self.assertIn(domain, gate.REQUIRED_ZERO_STATE_DOMAINS)

    def test_waiting_refresh_wait_blocks(self) -> None:
        path = _quiescent_database(self.tmp_path)
        stamp = NOW.isoformat()
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                """
                INSERT INTO printer_pre_lifecycle_discovery_refresh_waits (
                    wait_id, campaign_id, run_id, cycle_id, supervision_id,
                    scheduler_job_id, refresh_ordinal, wait_state, scheduled_for,
                    acquisition_deadline_at, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "wait-waiting",
                    "campaign-wait",
                    "run-wait",
                    "cycle-2",
                    "supervision-wait",
                    1,
                    1,
                    "WAITING",
                    stamp,
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
            self._assert_ready(path)
        self.assertIn("active_pre_lifecycle_discovery_refresh_waits", str(caught.exception))

    def test_claimed_refresh_wait_blocks(self) -> None:
        path = _quiescent_database(self.tmp_path)
        stamp = NOW.isoformat()
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                """
                INSERT INTO printer_pre_lifecycle_discovery_refresh_waits (
                    wait_id, campaign_id, run_id, cycle_id, supervision_id,
                    scheduler_job_id, refresh_ordinal, wait_state, scheduled_for,
                    acquisition_deadline_at, created_at, updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    "wait-claimed",
                    "campaign-claimed",
                    "run-claimed",
                    "cycle-2",
                    "supervision-claimed",
                    1,
                    1,
                    "CLAIMED",
                    stamp,
                    stamp,
                    stamp,
                    stamp,
                ),
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
            self._assert_ready(path)
        self.assertIn("active_pre_lifecycle_discovery_refresh_waits", str(caught.exception))

    def test_residual_active_campaign_work_blocks(self) -> None:
        path = _quiescent_database(self.tmp_path)
        connection = sqlite3.connect(path)
        try:
            connection.execute(
                "INSERT INTO printer_memory_factory_campaigns("
                "campaign_id,campaign_state,db_mode,db_target_identity,"
                "policy_version) VALUES "
                "('residue','RUNNING','OPERATIONAL_PERSISTENT','db-1','p-1')"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
            self._assert_ready(path)
        self.assertIn("active_campaigns", str(caught.exception))

    def test_running_printer_process_blocks(self) -> None:
        path = _quiescent_database(self.tmp_path)
        with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
            self._assert_ready(path, printer_process_probe=lambda: (4242,))
        self.assertIn("printer_process_present", str(caught.exception))

    def test_database_identity_drift_blocks_before_consumption(self) -> None:
        path = _quiescent_database(self.tmp_path)
        document = _document(path)
        document["authoritative_database"] = {
            **document["authoritative_database"],
            "sha256": "d" * 64,
        }
        with self.assertRaises(gate.FourTokenProofZeroStateError):
            self._assert_ready(path, authorization_document=document)

    def test_non_proof_authorization_document_is_rejected(self) -> None:
        path = _quiescent_database(self.tmp_path)
        document = _document(path)
        document["proof_policy"] = {
            **document["proof_policy"],
            "configured_through_4h_tokens": 6,
        }
        with self.assertRaises(gate.FourTokenProofZeroStateError):
            self._assert_ready(path, authorization_document=document)

    def test_invalid_source_configuration_blocks(self) -> None:
        # An absent RPC URL is the documented public fallback and stays valid.
        # A present but malformed one must block before consumption.
        path = _quiescent_database(self.tmp_path)
        for value in ("http://insecure.example", "YOUR_RPC_URL_HERE"):
            with self.subTest(rpc_url=value):
                with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
                    self._assert_ready(
                        path, environment={"PRINTER_SOLANA_RPC_URL": value}
                    )
                self.assertIn("source_configuration", str(caught.exception))

    def test_long_windows_remain_locked(self) -> None:
        self.assertEqual(
            gate.LOCKED_LONG_WINDOWS, ("WINDOW_12H", "WINDOW_24H")
        )
        path = _quiescent_database(self.tmp_path)
        evidence = self._assert_ready(path)
        self.assertEqual(
            evidence["locked_windows"], ["WINDOW_12H", "WINDOW_24H"]
        )


class FourTokenProofSupervisionZeroStateSemanticsTests(unittest.TestCase):
    """Zero supervision means zero *active* ownership, not destroyed history.

    Migration 033 keeps campaign supervision rows in ``TERMINAL`` and defines
    active ownership as ``ACTIVE``/``STOPPING``. Migration 030 keeps proof
    supervision rows in ``TERMINAL`` and defines active proof ownership as
    ``STARTING``/``RUNNING``. A healthy quiescent authoritative database is
    therefore expected to carry historical terminal supervision evidence.
    """

    def setUp(self) -> None:
        import tempfile
        from pathlib import Path

        self._tmp = tempfile.TemporaryDirectory()
        self.tmp_path = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def _assert_ready(self, path):
        return gate.assert_four_token_proof_zero_state(
            db_path=path,
            authorization_document=_document(path),
            environment=dict(ENVIRONMENT),
            printer_process_probe=lambda: (),
            migrations_dir=None,
        )

    def _database(self, populate):
        path = self.tmp_path / "supervision-zero-state.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        try:
            populate(connection)
            connection.commit()
        finally:
            connection.close()
        return path

    def test_historical_terminal_supervision_does_not_block(self) -> None:
        def populate(connection):
            _campaign_supervision_row(connection, supervision_state="TERMINAL")
            _proof_supervision_row(connection, execution_status="TERMINAL")

        path = self._database(populate)
        before = path.stat()
        evidence = self._assert_ready(path)
        self.assertIs(evidence["zero_state_ready"], True)
        self.assertEqual(evidence["zero_state_domains"]["campaign_supervision"], 0)
        self.assertEqual(evidence["zero_state_domains"]["proof_supervision"], 0)

        # Historical evidence must survive untouched; nothing is deleted or
        # rewritten to authorize a new bounded proof.
        after = path.stat()
        self.assertEqual(after.st_mtime_ns, before.st_mtime_ns)
        connection = sqlite3.connect(path)
        try:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM "
                    "printer_memory_factory_campaign_supervision"
                ).fetchone()[0],
                1,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_proof_run_supervision"
                ).fetchone()[0],
                1,
            )
        finally:
            connection.close()

    def test_active_campaign_supervision_still_blocks(self) -> None:
        for state in ("ACTIVE", "STOPPING"):
            with self.subTest(supervision_state=state):
                self.tmp_path = self.tmp_path / state
                self.tmp_path.mkdir()

                def populate(connection, state=state):
                    _campaign_supervision_row(
                        connection,
                        supervision_state=state,
                        campaign_state="RUNNING",
                        run_state="RUNNING",
                    )

                path = self._database(populate)
                with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
                    self._assert_ready(path)
                self.assertIn("campaign_supervision", str(caught.exception))
                self.tmp_path = self.tmp_path.parent

    def test_starting_or_running_proof_supervision_still_blocks(self) -> None:
        for status in ("STARTING", "RUNNING"):
            with self.subTest(execution_status=status):
                self.tmp_path = self.tmp_path / status
                self.tmp_path.mkdir()

                def populate(connection, status=status):
                    _proof_supervision_row(connection, execution_status=status)

                path = self._database(populate)
                with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
                    self._assert_ready(path)
                self.assertIn("proof_supervision", str(caught.exception))
                self.tmp_path = self.tmp_path.parent


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
