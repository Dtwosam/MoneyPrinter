"""V2-9.4 durable supervision and zero-source recovery tests."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.db import migrate as migration_runner
from printer_v1.operator_cli.one_command_15m_factory import load_report_only
from printer_v1.operator_cli.proof_supervision import (
    HOST_PROCESS_DISAPPEARED,
    OPERATOR_CANCELLED,
    OWNER_TEST_FIXTURE,
    ProofSupervisionError,
    TERMINAL_BUDGET_STOP,
    TERMINAL_COMPLETED,
    TERMINAL_GOVERNED_SAFE_STOP,
    TERMINAL_HOST_DISAPPEARED,
    TERMINAL_OPERATOR_CANCELLED,
    TERMINAL_SOURCE_FAILURE,
    attach_run,
    cancel_execution,
    create_execution,
    finalize_execution_from_report,
    heartbeat_execution,
    inspect_execution,
    recover_abandoned_execution,
)
from printer_v1.operator_cli.proof_db_schema_readiness import (
    validate_runtime_schema,
)


T0 = datetime(2026, 7, 16, 8, 0, tzinfo=timezone.utc)


class DurableSupervisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.temp.name)
        self.db = self.root / "proof.sqlite3"
        self.backup = self.root / "proof.backup.sqlite3"
        self.lock = self.root / "one-proof.lock.json"
        self.stdout = self.root / "proof.stdout.log"
        self.stderr = self.root / "proof.stderr.log"
        apply_migrations(self.db)
        shutil.copy2(self.db, self.backup)
        self.execution_id = "execution-v2-9-4"

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _create(self, execution_id: str | None = None) -> str:
        identifier = execution_id or self.execution_id
        report = create_execution(
            self.db,
            execution_id=identifier,
            owner_launcher_type=OWNER_TEST_FIXTURE,
            process_id=424242,
            backup_db_path=self.backup,
            one_proof_lock_path=self.lock,
            stdout_log_path=self.stdout,
            stderr_log_path=self.stderr,
            lease_seconds=30,
            now=T0,
        )
        self.assertEqual(report["execution_status"], "STARTING")
        self.assertEqual(report["owner_launcher_type"], OWNER_TEST_FIXTURE)
        self.assertEqual(report["process_id"], 424242)
        self.assertTrue(self.lock.is_file())
        return identifier

    def _attach_run(self, step_kind: str, *, running: bool = False) -> str:
        self._create()
        run_id = f"run-{step_kind.lower()}"
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                """INSERT INTO printer_memory_factory_runs
                   (run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at,created_at,updated_at)
                   VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}',?,?,?)""",
                (run_id, T0.isoformat(), T0.isoformat(), T0.isoformat()),
            )
            connection.commit()
        attach_run(
            self.db, self.execution_id, run_id,
            process_id=424242, lease_seconds=30, now=T0,
        )
        job_status = "RUNNING" if running else "PENDING"
        with closing(sqlite3.connect(self.db)) as connection:
            job_id = int(connection.execute(
                """INSERT INTO printer_scheduler_jobs
                   (job_name,job_kind,status,scheduled_for,locked_at,lock_owner)
                   VALUES (?,?,?,?,?,?)""",
                (
                    "proof-step", "MEMORY_WINDOW_CLOSE" if "CLOSE" in step_kind
                    else "TOKEN_SNAPSHOT", job_status, T0.isoformat(),
                    T0.isoformat() if running else None,
                    "fixture-owner" if running else None,
                ),
            ).lastrowid)
            connection.execute(
                """INSERT INTO printer_memory_factory_run_steps
                   (run_id,step_key,step_kind,step_status,tracking_lane,
                    scheduled_for,scheduler_job_id,started_at)
                   VALUES (?,'abandoned',?,?, 'TRACK_FAST',?,?,?)""",
                (
                    run_id, step_kind, job_status, T0.isoformat(), job_id,
                    T0.isoformat() if running else None,
                ),
            )
            connection.commit()
        return run_id

    def _assert_disappearance(self, step_kind: str, *, running: bool = False) -> None:
        run_id = self._attach_run(step_kind, running=running)
        before = self.db.read_bytes()
        report = recover_abandoned_execution(
            self.db,
            self.execution_id,
            process_probe=lambda _pid: False,
            now=T0 + timedelta(seconds=31),
        )
        self.assertEqual(report["terminal_status"], TERMINAL_HOST_DISAPPEARED)
        self.assertEqual(report["first_stop_reason"], HOST_PROCESS_DISAPPEARED)
        self.assertTrue(report["heartbeat_expired"])
        self.assertTrue(report["process_absent"])
        self.assertEqual(report["source_calls"], 0)
        self.assertEqual(report["automatic_retries"], 0)
        self.assertFalse(report["successor_created"])
        self.assertFalse(any(report["evidence_deltas"].values()))
        self.assertEqual(report["pending_or_running_steps_after"], 0)
        self.assertEqual(report["pending_or_running_jobs_after"], 0)
        self.assertTrue(report["released_scheduler_locks"])
        self.assertTrue(report["one_proof_lock_released"])
        self.assertFalse(self.lock.exists())
        supervision = inspect_execution(
            self.db, self.execution_id, now=T0 + timedelta(seconds=31)
        )
        self.assertIsNone(supervision["process_id"])
        self.assertEqual(supervision["lease_expires_at"], report["finished_at"])
        self.assertNotEqual(before, self.db.read_bytes())

        with closing(sqlite3.connect(self.db)) as connection:
            connection.row_factory = sqlite3.Row
            step = connection.execute(
                "SELECT * FROM printer_memory_factory_run_steps WHERE run_id=?",
                (run_id,),
            ).fetchone()
            job = connection.execute(
                "SELECT * FROM printer_scheduler_jobs WHERE id=?",
                (step["scheduler_job_id"],),
            ).fetchone()
            run = connection.execute(
                "SELECT * FROM printer_memory_factory_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
            self.assertEqual(step["step_status"], "CANCELLED")
            self.assertEqual(step["error_or_skip_reason"], HOST_PROCESS_DISAPPEARED)
            self.assertEqual(job["status"], "CANCELLED")
            self.assertIsNone(job["locked_at"])
            self.assertIsNone(job["lock_owner"])
            self.assertEqual(run["run_status"], "FAILED")
            self.assertEqual(run["stop_reason"], HOST_PROCESS_DISAPPEARED)
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_windows"
                ).fetchone()[0],
                0,
            )
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM printer_memory_fingerprints"
                ).fetchone()[0],
                0,
            )

        replay = load_report_only(self.db, run_id)
        self.assertEqual(replay["stop_reason"], HOST_PROCESS_DISAPPEARED)
        self.assertEqual(
            replay["replay"],
            {"mode": "REPORT_ONLY", "new_source_calls": 0, "new_evidence_rows": 0},
        )
        second = recover_abandoned_execution(
            self.db,
            self.execution_id,
            process_probe=lambda _pid: False,
            now=T0 + timedelta(seconds=60),
        )
        self.assertTrue(second["idempotent_replay"])

    def test_disappearance_during_15m(self) -> None:
        self._assert_disappearance("SNAPSHOT")

    def test_disappearance_during_1h_continuation(self) -> None:
        self._assert_disappearance("CONTINUATION_SNAPSHOT")

    def test_disappearance_during_4h_continuation(self) -> None:
        self._assert_disappearance("LONG_CONTINUATION_SNAPSHOT")

    def test_disappearance_during_forced_close_releases_running_lock(self) -> None:
        self._assert_disappearance("LONG_CONTINUATION_CLOSE", running=True)

    def test_heartbeat_renews_lease_and_live_process_blocks_recovery(self) -> None:
        self._attach_run("CONTINUATION_SNAPSHOT")
        heartbeat = heartbeat_execution(
            self.db, self.execution_id, process_id=424242,
            lease_seconds=30, now=T0 + timedelta(seconds=10),
        )
        self.assertEqual(heartbeat["heartbeat_at"], (T0 + timedelta(seconds=10)).isoformat())
        self.assertFalse(
            inspect_execution(
                self.db, self.execution_id, now=T0 + timedelta(seconds=39)
            )["lease_expired"]
        )
        with self.assertRaisesRegex(ProofSupervisionError, "still alive"):
            recover_abandoned_execution(
                self.db, self.execution_id,
                process_probe=lambda _pid: True,
                now=T0 + timedelta(seconds=41),
            )

    def test_operator_cancellation_cleans_without_waiting_for_expiry(self) -> None:
        run_id = self._attach_run("CONTINUATION_SNAPSHOT")
        report = cancel_execution(
            self.db, self.execution_id,
            process_probe=lambda _pid: False,
            now=T0 + timedelta(seconds=5),
        )
        self.assertEqual(report["terminal_status"], TERMINAL_OPERATOR_CANCELLED)
        self.assertEqual(report["first_stop_reason"], OPERATOR_CANCELLED)
        self.assertEqual(report["pending_or_running_jobs_after"], 0)
        replay = load_report_only(self.db, run_id)
        self.assertEqual(replay["run_status"], "SAFE_STOPPED")

    def test_normal_and_governed_terminal_status_mapping(self) -> None:
        cases = (
            ("COMPLETED", "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED", TERMINAL_COMPLETED),
            ("FAILED", "SAFE_STOP_SOURCE_FAILURE", TERMINAL_SOURCE_FAILURE),
            ("SAFE_STOPPED", "SAFE_STOP_BUDGET_CEILING_EXCEEDED", TERMINAL_BUDGET_STOP),
            ("SAFE_STOPPED", "SAFE_STOP_4H_TERMINAL_INCOMPLETE", TERMINAL_GOVERNED_SAFE_STOP),
        )
        for index, (run_status, reason, expected) in enumerate(cases):
            with self.subTest(expected=expected):
                if index:
                    self.db = self.root / f"proof-{index}.sqlite3"
                    self.backup = self.root / f"proof-{index}.backup.sqlite3"
                    self.lock = self.root / f"lock-{index}.json"
                    apply_migrations(self.db)
                    shutil.copy2(self.db, self.backup)
                    self.execution_id = f"execution-{index}"
                self._create()
                finalized = finalize_execution_from_report(
                    self.db,
                    self.execution_id,
                    {"run_status": run_status, "stop_reason": reason},
                    now=T0 + timedelta(seconds=1),
                )
                self.assertEqual(finalized["terminal_status"], expected)
                self.assertEqual(finalized["first_stop_reason"], reason)
                self.assertFalse(self.lock.exists())

    def test_new_proof_rejected_while_abandoned_run_is_unresolved(self) -> None:
        self._attach_run("CONTINUATION_SNAPSHOT")
        other_db = self.root / "other.sqlite3"
        other_backup = self.root / "other.backup.sqlite3"
        apply_migrations(other_db)
        shutil.copy2(other_db, other_backup)
        with self.assertRaisesRegex(ProofSupervisionError, "active or unresolved"):
            create_execution(
                other_db,
                execution_id="other-execution",
                owner_launcher_type=OWNER_TEST_FIXTURE,
                process_id=515151,
                backup_db_path=other_backup,
                one_proof_lock_path=self.lock,
                stdout_log_path=self.stdout,
                stderr_log_path=self.stderr,
                lease_seconds=30,
                now=T0 + timedelta(hours=1),
            )

    def test_schema_and_launcher_contracts_are_canonical_and_locked(self) -> None:
        schema = validate_runtime_schema(self.db)
        self.assertTrue(schema["runtime_ready"])
        # V2-9.7E.7: derive the expected head from the authoritative migration
        # owner instead of pinning a literal. The previous literal ("030") was
        # stale from migration 031 onward and asserted a head the repository no
        # longer had. A new literal would go stale the same way.
        canonical = [
            path.name for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql"))
        ]
        self.assertEqual(schema["latest_migration"], canonical[-1])
        # Ordering stays locked: the canonical registry must be lexicographically
        # ordered, and every canonical migration must be applied. Any missing,
        # unknown, or renumbered migration already fails runtime_ready above.
        self.assertEqual(canonical, sorted(canonical))
        self.assertEqual(
            schema["applied_migration_count"], schema["canonical_migration_count"]
        )
        self.assertEqual(schema["canonical_migration_count"], len(canonical))
        launcher = (
            Path(__file__).resolve().parents[1] / "scripts" / "Start-V2-9-Proof.ps1"
        ).read_text(encoding="utf-8")
        self.assertEqual(launcher.count("printer_v1.operator_cli.proof_db_schema_readiness"), 1)
        self.assertEqual(launcher.count("Start-Process"), 1)
        self.assertIn("'heartbeat'", launcher)
        self.assertIn("'recover'", launcher)
        self.assertIn("'cancel'", launcher)
        self.assertIn("SetThreadExecutionState", launcher)
        self.assertIn("operator-runs", launcher)
        self.assertNotIn("--token", launcher)
        self.assertNotIn("--pair", launcher)
        self.assertNotIn("--predecessor", launcher)
        self.assertNotIn("WINDOW_12H", launcher)
        self.assertNotIn("WINDOW_24H", launcher)


if __name__ == "__main__":
    unittest.main()
