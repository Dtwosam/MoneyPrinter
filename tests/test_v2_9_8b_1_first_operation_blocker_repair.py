from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import operational_memory_factory_command as command
from printer_v1.operator_cli.campaign_supervision import (
    acquire_campaign_supervision,
    request_campaign_cancellation,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.operational_campaign_recovery import (
    OperationalCampaignRecoveryError,
    OrphanRecoveryContract,
    _canonical_rows_hash,
    _read_only,
    _rows,
    recover_exact_orphan,
)


class _PostInitializationFailure(RuntimeError):
    pass


class _FailingOwner:
    def run_operational(self, **_kwargs):
        raise _PostInitializationFailure("disposable post-init fault")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _provenance() -> dict[str, object]:
    return {
        "git_head": "a" * 40,
        "git_tracked_tree_clean": True,
        "git_staged_changes_present": False,
        "git_unstaged_changes_present": False,
        "git_untracked_present": False,
        "git_provenance_captured_at": "2026-07-26T11:41:55+00:00",
    }


class FirstOperationBlockerRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.baseline = self.root / "pre-campaign.sqlite3"
        apply_migrations(self.baseline)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _new_current(self) -> Path:
        current = self.root / f"current-{len(list(self.root.glob('current-*')))}.sqlite3"
        shutil.copy2(self.baseline, current)
        return current

    def _paths(self, name: str) -> dict[str, Path]:
        root = self.root / name
        root.mkdir()
        reports = root / "reports"
        reports.mkdir()
        return {
            "root": root,
            "backup": root / "pre.sqlite3",
            "restore": root / "restore.sqlite3",
            "reports": reports,
            "lock": root / "campaign.lease.lock",
            "stdout": root / "stdout.log",
            "stderr": root / "stderr.log",
            "summary": root / "terminal-summary.json",
        }

    def _create_orphan(
        self, name: str = "orphan"
    ) -> tuple[Path, dict[str, Path], OrphanRecoveryContract]:
        current = self._new_current()
        paths = self._paths(name)
        execution_id = f"20260726T114155Z-{name}"
        preflight = {
            "database_sha256": _sha256(current),
            "git_provenance": _provenance(),
        }
        backup = {
            "source_identity": f"sha256:{_sha256(current)}",
            "backup_hash": _sha256(current),
            "latest_rehearsed_migration": "042_held_to_15m_moderate_continuation.sql",
        }
        started = "2026-07-26T11:41:56+00:00"
        with patch.object(command, "AUTHORITATIVE_DB", current.resolve()):
            campaign_command, _cycle = command._create_campaign_command(
                execution_id=execution_id,
                paths=paths,
                preflight=preflight,
                backup=backup,
                now=started,
            )
        acquire_campaign_supervision(
            current,
            lock_path=paths["lock"],
            supervision_id=campaign_command.supervision_id,
            campaign_id=campaign_command.campaign_id,
            configuration_id=campaign_command.configuration_id,
            run_id=campaign_command.run_id,
            owner_id=campaign_command.owner_id,
            lease_seconds=90,
            now=datetime(2026, 7, 26, 11, 41, 56, tzinfo=timezone.utc),
        )
        request_campaign_cancellation(
            current,
            supervision_id=campaign_command.supervision_id,
            campaign_id=campaign_command.campaign_id,
            configuration_id=campaign_command.configuration_id,
            run_id=campaign_command.run_id,
            owner_id=campaign_command.owner_id,
            reason="OPERATOR_REQUESTED_COOPERATIVE_STOP",
            now=datetime(2026, 7, 26, 11, 54, 51, tzinfo=timezone.utc),
        )
        graph_tables = (
            "printer_memory_factory_campaigns",
            "printer_memory_factory_campaign_configurations",
            "printer_memory_factory_campaign_runs",
            "printer_memory_factory_campaign_cycles",
            "printer_memory_factory_campaign_supervision",
        )
        connection = _read_only(current)
        try:
            hashes = {
                table: _canonical_rows_hash(_rows(connection, table))
                for table in graph_tables
            }
        finally:
            connection.close()
        contract = OrphanRecoveryContract(
            execution_id=execution_id,
            expected_current_sha256=_sha256(current),
            pre_campaign_backup_sha256=_sha256(self.baseline),
            expected_graph_table_hashes=hashes,
        )
        return current, paths, contract

    def test_post_initialization_exception_re_raises_original_after_terminalization(self):
        current = self._new_current()
        artifact_root = self.root / "post-init-artifacts"
        preflight = {
            "database_sha256": _sha256(current),
            "git_provenance": _provenance(),
        }
        backup = {
            "source_identity": f"sha256:{_sha256(current)}",
            "backup_hash": _sha256(current),
            "latest_rehearsed_migration": "042_held_to_15m_moderate_continuation.sql",
        }
        with (
            patch.object(command, "AUTHORITATIVE_DB", current.resolve()),
            patch.object(command, "ARTIFACT_ROOT", artifact_root),
            patch.object(command, "build_activation_preflight", return_value=preflight),
            patch.object(
                command, "operational_backup_restore_preflight", return_value=backup
            ),
            patch.object(command._CampaignHeartbeat, "start", return_value=None),
            patch.object(command._CampaignHeartbeat, "stop", return_value=None),
        ):
            with self.assertRaises(_PostInitializationFailure):
                command.run_operational_campaign(
                    operator_approved=True,
                    owner=_FailingOwner(),
                    pump_transport=object(),
                    secondary_transport=object(),
                    migration_transport=object(),
                )
        connection = sqlite3.connect(current)
        try:
            campaign = connection.execute(
                "SELECT campaign_state,first_terminal_cause "
                "FROM printer_memory_factory_campaigns"
            ).fetchone()
            supervision = connection.execute(
                "SELECT supervision_state,terminal_status,first_terminal_cause,"
                "cleanup_completed_at,lease_released_at "
                "FROM printer_memory_factory_campaign_supervision"
            ).fetchone()
            reports = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
            ).fetchone()[0]
        finally:
            connection.close()
        expected = "OPERATIONAL_CAMPAIGN_FAILED:_PostInitializationFailure"
        self.assertEqual(("TERMINAL_FAILED", expected), campaign)
        self.assertEqual("TERMINAL", supervision[0])
        self.assertEqual("FAILED", supervision[1])
        self.assertEqual(expected, supervision[2])
        self.assertIsNotNone(supervision[3])
        self.assertIsNotNone(supervision[4])
        self.assertEqual(1, reports)
        self.assertFalse(any(artifact_root.glob("*/campaign.lease.lock")))

    def test_recovery_rejects_wrong_sha_ids_live_process_and_live_lease(self):
        for case in ("sha", "ids", "process", "lease"):
            with self.subTest(case=case):
                current, paths, contract = self._create_orphan(f"reject-{case}")
                kwargs = {
                    "operator_approved": True,
                    "current_db": current,
                    "pre_campaign_backup": self.baseline,
                    "artifact_root": paths["root"],
                    "recovery_root": self.root / f"recovery-{case}",
                    "contract": contract,
                    "live_process_probe": lambda _execution: False,
                    "now": datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
                }
                if case == "sha":
                    kwargs["contract"] = OrphanRecoveryContract(
                        execution_id=contract.execution_id,
                        expected_current_sha256="0" * 64,
                        pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
                        expected_graph_table_hashes=contract.expected_graph_table_hashes,
                    )
                elif case == "ids":
                    kwargs["contract"] = OrphanRecoveryContract(
                        execution_id="wrong-execution",
                        expected_current_sha256=contract.expected_current_sha256,
                        pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
                        expected_graph_table_hashes=contract.expected_graph_table_hashes,
                    )
                elif case == "process":
                    kwargs["live_process_probe"] = lambda _execution: True
                else:
                    kwargs["now"] = datetime(
                        2026, 7, 26, 11, 42, tzinfo=timezone.utc
                    )
                with self.assertRaises(OperationalCampaignRecoveryError):
                    recover_exact_orphan(**kwargs)

    def test_recovery_rejects_active_scheduler_and_unexpected_row_delta(self):
        current, paths, contract = self._create_orphan("active-scheduler")
        connection = sqlite3.connect(current)
        try:
            connection.execute(
                """INSERT INTO printer_scheduler_jobs(
                       job_name,job_kind,status,scheduled_for
                   ) VALUES ('unexpected-active','TRACK_FAST_FIRST_15M',
                             'PENDING','2026-07-26T12:00:00+00:00')"""
            )
            connection.commit()
        finally:
            connection.close()
        active_contract = OrphanRecoveryContract(
            execution_id=contract.execution_id,
            expected_current_sha256=_sha256(current),
            pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
            expected_graph_table_hashes=contract.expected_graph_table_hashes,
        )
        with patch(
            "printer_v1.operator_cli.operational_campaign_recovery."
            "_assert_exact_pre_recovery_delta",
            return_value={"changed_tables": [], "unchanged_tables": 0},
        ):
            with self.assertRaisesRegex(
                OperationalCampaignRecoveryError, "Scheduler"
            ):
                recover_exact_orphan(
                    operator_approved=True,
                    current_db=current,
                    pre_campaign_backup=self.baseline,
                    artifact_root=paths["root"],
                    recovery_root=self.root / "recovery-active",
                    contract=active_contract,
                    live_process_probe=lambda _execution: False,
                    now=datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
                )

        current, paths, contract = self._create_orphan("unexpected-delta")
        connection = sqlite3.connect(current)
        try:
            connection.execute(
                "UPDATE printer_schema_migrations SET applied_at='unexpected' "
                "WHERE rowid=(SELECT MIN(rowid) FROM printer_schema_migrations)"
            )
            connection.commit()
        finally:
            connection.close()
        drift_contract = OrphanRecoveryContract(
            execution_id=contract.execution_id,
            expected_current_sha256=_sha256(current),
            pre_campaign_backup_sha256=contract.pre_campaign_backup_sha256,
            expected_graph_table_hashes=contract.expected_graph_table_hashes,
        )
        with self.assertRaisesRegex(
            OperationalCampaignRecoveryError, "unexpected database row delta"
        ):
            recover_exact_orphan(
                operator_approved=True,
                current_db=current,
                pre_campaign_backup=self.baseline,
                artifact_root=paths["root"],
                recovery_root=self.root / "recovery-delta",
                contract=drift_contract,
                live_process_probe=lambda _execution: False,
                now=datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
            )

    def test_disposable_recovery_preserves_locks_and_is_idempotent(self):
        current, paths, contract = self._create_orphan("success")
        connection = sqlite3.connect(current)
        connection.row_factory = sqlite3.Row
        try:
            locked_before = {
                table: [dict(row) for row in connection.execute(
                    f"SELECT * FROM {table}"
                ).fetchall()]
                for table in LOCKED_CAPABILITY_TABLES
            }
        finally:
            connection.close()
        arguments = {
            "operator_approved": True,
            "current_db": current,
            "pre_campaign_backup": self.baseline,
            "artifact_root": paths["root"],
            "recovery_root": self.root / "recovery-success",
            "contract": contract,
            "live_process_probe": lambda _execution: False,
            "now": datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc),
        }
        result = recover_exact_orphan(**arguments)
        self.assertEqual("V2_9_8B_1_ORPHAN_RECOVERED", result["status"])
        self.assertEqual(0, result["source_calls"])
        self.assertFalse(result["restart_created"])
        self.assertFalse(result["successor_created"])
        final_sha = _sha256(current)

        replay = recover_exact_orphan(**arguments)
        self.assertEqual(
            "V2_9_8B_1_ORPHAN_ALREADY_RECOVERED", replay["status"]
        )
        self.assertEqual(final_sha, _sha256(current))
        connection = sqlite3.connect(current)
        connection.row_factory = sqlite3.Row
        try:
            locked_after = {
                table: [dict(row) for row in connection.execute(
                    f"SELECT * FROM {table}"
                ).fetchall()]
                for table in LOCKED_CAPABILITY_TABLES
            }
            report_count = connection.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_campaign_reports"
            ).fetchone()[0]
        finally:
            connection.close()
        self.assertEqual(locked_before, locked_after)
        self.assertEqual(1, report_count)


if __name__ == "__main__":
    unittest.main()
