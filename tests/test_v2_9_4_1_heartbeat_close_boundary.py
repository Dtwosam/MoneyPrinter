"""V2-9.4.1 heartbeat and close-boundary supervision fixtures."""

from __future__ import annotations

from contextlib import closing
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.proof_supervision import (
    HOST_PROCESS_DISAPPEARED,
    OWNER_TEST_FIXTURE,
    SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED,
    TERMINAL_GOVERNED_SAFE_STOP,
    attach_run,
    cooperative_stop_reason,
    create_execution,
    heartbeat_active_lease,
    inspect_execution,
    recover_abandoned_execution,
    request_cooperative_stop,
    stop_execution,
)


T0 = datetime(2026, 7, 16, 11, 34, 23, tzinfo=timezone.utc)


class HeartbeatCloseBoundarySupervisionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.root = Path(self.temp.name)
        self.db = self.root / "proof.sqlite3"
        self.backup = self.root / "proof.backup.sqlite3"
        self.lock = self.root / "one-proof.lock.json"
        apply_migrations(self.db)
        shutil.copy2(self.db, self.backup)
        self.execution_id = "execution-v2-9-4-1"
        create_execution(
            self.db,
            execution_id=self.execution_id,
            owner_launcher_type=OWNER_TEST_FIXTURE,
            process_id=424242,
            backup_db_path=self.backup,
            one_proof_lock_path=self.lock,
            stdout_log_path=self.root / "stdout.log",
            stderr_log_path=self.root / "stderr.log",
            lease_seconds=90,
            now=T0,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _attach_empty_run(self, *, status: str = "RUNNING", report: dict | None = None) -> str:
        run_id = "run-v2-9-4-1"
        now = T0.isoformat()
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                """INSERT INTO printer_memory_factory_runs
                   (run_id,run_status,window_kind,db_mode,config_hash,config_json,
                    started_at,finished_at,final_report_json,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    status,
                    "WINDOW_15M",
                    "PROOF_ONLY",
                    "hash",
                    "{}",
                    now,
                    now if status != "RUNNING" else None,
                    json.dumps(report, sort_keys=True) if report is not None else None,
                    now,
                    now,
                ),
            )
            connection.commit()
        attach_run(
            self.db,
            self.execution_id,
            run_id,
            process_id=424242,
            lease_seconds=90,
            now=T0,
        )
        return run_id

    def test_lock_lease_heartbeat_succeeds_while_proof_db_has_write_contention(self) -> None:
        with closing(sqlite3.connect(self.db, timeout=0.01)) as writer:
            writer.execute("BEGIN IMMEDIATE")
            renewed = heartbeat_active_lease(
                self.lock,
                self.execution_id,
                process_id=424242,
                lease_seconds=90,
                now=T0 + timedelta(seconds=30),
            )
            self.assertEqual(
                renewed["heartbeat_at"],
                (T0 + timedelta(seconds=30)).isoformat(),
            )
            self.assertEqual(
                renewed["lease_expires_at"],
                (T0 + timedelta(seconds=120)).isoformat(),
            )
            inspected = inspect_execution(
                self.db,
                self.execution_id,
                now=T0 + timedelta(seconds=31),
            )
            self.assertFalse(inspected["lease_expired"])
            self.assertEqual(inspected["heartbeat_at"], renewed["heartbeat_at"])
            writer.rollback()

    def test_supervision_fault_preserves_exact_non_operator_first_cause(self) -> None:
        self._attach_empty_run()
        requested = request_cooperative_stop(
            self.lock,
            self.execution_id,
            stop_reason=SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED,
            now=T0 + timedelta(seconds=60),
        )
        self.assertEqual(
            requested["cancellation_reason"],
            SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED,
        )
        self.assertEqual(
            cooperative_stop_reason(self.lock, self.execution_id),
            SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED,
        )
        stopped = stop_execution(
            self.db,
            self.execution_id,
            stop_reason=SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED,
            process_probe=lambda _pid: False,
            now=T0 + timedelta(seconds=61),
        )
        self.assertEqual(stopped["terminal_status"], TERMINAL_GOVERNED_SAFE_STOP)
        self.assertEqual(
            stopped["first_stop_reason"],
            SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED,
        )
        self.assertNotEqual(stopped["first_stop_reason"], "OPERATOR_CANCELLED")
        self.assertEqual(stopped["pending_or_running_jobs_after"], 0)

    def test_recovery_reports_full_run_and_recovery_deltas_separately(self) -> None:
        self._attach_empty_run()
        with closing(sqlite3.connect(self.db)) as connection:
            connection.execute(
                """INSERT INTO printer_source_requests
                   (source_name,request_kind,requested_at,source_status,data_quality_label)
                   VALUES ('dexscreener','fixture',?,'COMPLETE','CLEAN_DATA')""",
                (T0.isoformat(),),
            )
            connection.commit()
        report = recover_abandoned_execution(
            self.db,
            self.execution_id,
            process_probe=lambda _pid: False,
            now=T0 + timedelta(seconds=91),
        )
        self.assertEqual(report["first_stop_reason"], HOST_PROCESS_DISAPPEARED)
        self.assertEqual(
            report["full_run_evidence_deltas"]["printer_source_requests"],
            1,
        )
        self.assertTrue(
            all(value == 0 for value in report["recovery_evidence_deltas"].values())
        )
        self.assertEqual(
            report["evidence_deltas"],
            report["recovery_evidence_deltas"],
        )

    def test_late_recovery_does_not_overwrite_completed_full_report(self) -> None:
        completed = {
            "run_status": "COMPLETED",
            "stop_reason": "COMPLETED_CLEAN_OR_DIRTY_RESULTS_REPORTED",
            "full_run_evidence_deltas": {"printer_source_requests": 7},
        }
        run_id = self._attach_empty_run(status="COMPLETED", report=completed)
        recover_abandoned_execution(
            self.db,
            self.execution_id,
            process_probe=lambda _pid: False,
            now=T0 + timedelta(seconds=91),
        )
        with closing(sqlite3.connect(self.db)) as connection:
            row = connection.execute(
                "SELECT run_status,stop_reason,final_report_json "
                "FROM printer_memory_factory_runs WHERE run_id=?",
                (run_id,),
            ).fetchone()
        self.assertEqual(row[0], "COMPLETED")
        self.assertIsNone(row[1])
        self.assertEqual(json.loads(row[2]), completed)

    def test_unbuffered_interrupted_child_produces_usable_stdout_and_stderr(self) -> None:
        stdout_path = self.root / "fixture.stdout.log"
        stderr_path = self.root / "fixture.stderr.log"
        code = (
            "import sys,time,json;"
            "print(json.dumps({'event':'PROCESS_START'}),flush=True);"
            "print('fixture stderr marker',file=sys.stderr,flush=True);"
            "time.sleep(30)"
        )
        with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
            "w", encoding="utf-8"
        ) as stderr_handle:
            process = subprocess.Popen(
                [sys.executable, "-u", "-c", code],
                stdout=stdout_handle,
                stderr=stderr_handle,
            )
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                if stdout_path.exists() and stdout_path.stat().st_size:
                    break
                time.sleep(0.05)
            process.terminate()
            process.wait(timeout=5)
        self.assertIn("PROCESS_START", stdout_path.read_text(encoding="utf-8"))
        self.assertIn("fixture stderr marker", stderr_path.read_text(encoding="utf-8"))

    def test_launcher_contract_has_explicit_attempt_and_fault_boundaries(self) -> None:
        launcher = (
            Path(__file__).resolve().parents[1] / "scripts" / "Start-V2-9-Proof.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn("[int]$AttemptNumber", launcher)
        self.assertIn("v2-9-attempt$AttemptNumber", launcher)
        self.assertNotIn("attempt4", launcher)
        self.assertIn("'SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED'", launcher)
        self.assertIn("$heartbeatFailures -ge 2", launcher)
        self.assertIn("One failed renewal never kills", launcher)
        self.assertIn("'--lock-path', $lockPath", launcher)
        self.assertIn("'-u'", launcher)
        self.assertIn("$launcherLog", launcher)
        self.assertEqual(
            launcher.count("$operatorCancelled = $true"),
            1,
        )
        self.assertIn("catch [System.Management.Automation.PipelineStoppedException]", launcher)
        self.assertIn("FORCED_TERMINATION_AFTER_EXPIRED_LEASE", launcher)
        self.assertIn("automatic_retries = 0", launcher)


if __name__ == "__main__":
    unittest.main()
