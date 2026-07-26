from __future__ import annotations

from datetime import datetime, timezone
import hashlib
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest

from printer_v1.operator_cli.scheduler_residue_reconciliation import (
    ALLOWED_CHANGED_FIELDS,
    AUDITED_JOB_IDS,
    SchedulerResidueReconciliationError,
    classify_scheduler_residue,
    reconcile_scheduler_residue,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "printer_v1.sqlite3"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class SchedulerResidueReconciliationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "disposable.sqlite3"
        shutil.copy2(SOURCE, self.db)
        # The authoritative corpus is terminal after the one-time A.9 repair.
        # Recreate the audited pre-repair state explicitly in this disposable
        # fixture so the repair proof remains repeatable without depending on
        # live corpus state.
        connection = sqlite3.connect(self.db)
        placeholders = ",".join("?" * len(AUDITED_JOB_IDS))
        connection.execute(
            f"""UPDATE printer_scheduler_jobs
                SET status='PENDING',finished_at=NULL,locked_at=NULL,lock_owner=NULL,
                    updated_at=created_at
                WHERE id IN ({placeholders})""",
            AUDITED_JOB_IDS,
        )
        connection.commit()
        connection.close()
        self.before_hash = sha256(self.db)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_repair(self, **overrides):
        values = {
            "expected_authoritative_path": self.db,
            "expected_sha256": sha256(self.db),
            "job_ids": AUDITED_JOB_IDS,
            "operator_approved": True,
            "backup_path": self.root / f"backup-{len(list(self.root.glob('backup-*')))}.sqlite3",
            "disposable_restore_root": self.root,
            "restore_path": self.root / f"restore-{len(list(self.root.glob('restore-*')))}.sqlite3",
            "now": datetime(2026, 7, 26, 17, 0, tzinfo=timezone.utc),
        }
        values.update(overrides)
        return reconcile_scheduler_residue(self.db, **values)

    def test_exact_rows_allowed_fields_only_and_unrelated_preserved(self) -> None:
        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        before = {
            int(row["id"]): dict(row)
            for row in connection.execute(
                "SELECT * FROM printer_scheduler_jobs ORDER BY id"
            ).fetchall()
        }
        audit = tuple(
            connection.execute(
                "SELECT * FROM printer_paper_audit_reports ORDER BY id"
            ).fetchall()
        )
        connection.close()

        result = self.run_repair()
        self.assertEqual("SCHEDULER_RESIDUE_RECONCILED", result["status"])
        self.assertEqual(AUDITED_JOB_IDS, result["job_ids"])
        self.assertTrue(set(result["changed_fields"]).issubset(ALLOWED_CHANGED_FIELDS))
        self.assertEqual(0, result["source_calls"])
        self.assertEqual(0, result["campaigns_created"])

        connection = sqlite3.connect(self.db)
        connection.row_factory = sqlite3.Row
        after = {
            int(row["id"]): dict(row)
            for row in connection.execute(
                "SELECT * FROM printer_scheduler_jobs ORDER BY id"
            ).fetchall()
        }
        self.assertEqual(
            audit,
            tuple(
                connection.execute(
                    "SELECT * FROM printer_paper_audit_reports ORDER BY id"
                ).fetchall()
            ),
        )
        self.assertEqual("ok", connection.execute("PRAGMA integrity_check").fetchone()[0])
        self.assertEqual([], connection.execute("PRAGMA foreign_key_check").fetchall())
        connection.close()
        for job_id, row in before.items():
            if job_id in AUDITED_JOB_IDS:
                changed = {key for key in row if row[key] != after[job_id][key]}
                self.assertTrue(changed.issubset(ALLOWED_CHANGED_FIELDS))
                self.assertEqual("CANCELLED", after[job_id]["status"])
            else:
                self.assertEqual(row, after[job_id])

    def test_wrong_sha_changed_ids_missing_approval_fail_closed(self) -> None:
        with self.assertRaises(SchedulerResidueReconciliationError):
            self.run_repair(expected_sha256="0" * 64)
        with self.assertRaises(SchedulerResidueReconciliationError):
            self.run_repair(job_ids=AUDITED_JOB_IDS[:-1])
        with self.assertRaises(SchedulerResidueReconciliationError):
            self.run_repair(operator_approved=False)
        self.assertEqual(self.before_hash, sha256(self.db))

    def test_locked_or_linked_job_fails_closed(self) -> None:
        connection = sqlite3.connect(self.db)
        connection.execute(
            "UPDATE printer_scheduler_jobs SET locked_at='2026-07-26T00:00:00+00:00',"
            "lock_owner='foreign' WHERE id=8"
        )
        connection.commit()
        connection.close()
        with self.assertRaises(SchedulerResidueReconciliationError):
            self.run_repair()

    def test_idempotent_second_classification(self) -> None:
        first = self.run_repair()
        second = self.run_repair(expected_sha256=first["database_sha256_after"])
        self.assertEqual("ALREADY_RECONCILED", second["status"])
        connection = sqlite3.connect(self.db)
        classes = {row["classification"] for row in classify_scheduler_residue(connection)}
        connection.close()
        self.assertEqual({"RECONCILED_HISTORICAL_TERMINAL"}, classes)


if __name__ == "__main__":
    unittest.main()
