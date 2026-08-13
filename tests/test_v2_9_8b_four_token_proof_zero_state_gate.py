"""Focused contract for the read-only four-token proof pre-consumption gate.

Offline only. Every database in this file is a disposable temporary fixture.
The gate under test must be strictly read-only: it creates no campaign,
reservation, lease, discovery attempt, Scheduler job, or source request, starts
no Printer process, and never touches the authoritative database.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
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
        authorized_at=NOW.isoformat(),
        expires_at=(NOW + timedelta(hours=12)).isoformat(),
    )


def _quiescent_database(tmp_path):
    path = tmp_path / "four-token-zero-state.sqlite3"
    apply_migrations(path)
    return path


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

    def test_quiescent_post_055_database_passes_read_only(self) -> None:
        path = _quiescent_database(self.tmp_path)
        before = path.stat()
        evidence = self._assert_ready(path)
        after = path.stat()
        self.assertEqual(
            evidence["schema_version"], gate.ZERO_STATE_SCHEMA_VERSION
        )
        self.assertIs(evidence["zero_state_ready"], True)
        self.assertEqual(evidence["blockers"], [])
        self.assertEqual(evidence["migration_count"], 55)
        self.assertEqual(
            evidence["migration_head"],
            "055_pre_admission_discovery_attempt_ownership.sql",
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
            "active_scheduler_jobs",
        ):
            self.assertIn(domain, gate.REQUIRED_ZERO_STATE_DOMAINS)

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
        path = _quiescent_database(self.tmp_path)
        with self.assertRaises(gate.FourTokenProofZeroStateError) as caught:
            self._assert_ready(path, environment={})
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


if __name__ == "__main__":  # pragma: no cover - direct invocation guard
    unittest.main()
