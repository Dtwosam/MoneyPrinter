from __future__ import annotations

import sqlite3
import tempfile
import threading
import time
import unittest
from pathlib import Path

from printer_v1.operator_cli import operational_memory_factory_command as command


class PostDTW95CancellationProbeSQLiteContentionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.db_path = Path(self.tempdir.name) / "probe.sqlite3"
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """
                CREATE TABLE printer_memory_factory_campaign_supervision (
                    supervision_id TEXT NOT NULL,
                    campaign_id TEXT NOT NULL,
                    run_id TEXT NOT NULL,
                    supervision_state TEXT NOT NULL,
                    cancellation_reason TEXT
                )
                """
            )
            connection.execute(
                """INSERT INTO printer_memory_factory_campaign_supervision(
                       supervision_id,campaign_id,run_id,supervision_state,cancellation_reason
                   ) VALUES (?,?,?,?,?)""",
                ("sup", "campaign", "run", "ACTIVE", None),
            )
            connection.commit()
        finally:
            connection.close()

    def _probe(self, *, timeout: float = 0.5) -> str | None:
        return command._read_campaign_supervision_cancellation_reason(
            self.db_path,
            expected_path=self.db_path,
            supervision_id="sup",
            campaign_id="campaign",
            run_id="run",
            busy_timeout_seconds=timeout,
        )

    def _set_state(self, state: str, reason: str | None = None) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                """UPDATE printer_memory_factory_campaign_supervision
                   SET supervision_state=?, cancellation_reason=?
                   WHERE supervision_id='sup'""",
                (state, reason),
            )
            connection.commit()
        finally:
            connection.close()

    def test_short_writer_contention_is_tolerated(self) -> None:
        writer = sqlite3.connect(
            self.db_path, timeout=0.0, check_same_thread=False
        )
        writer.execute("BEGIN EXCLUSIVE")

        def release() -> None:
            time.sleep(0.10)
            writer.commit()
            writer.close()

        thread = threading.Thread(target=release)
        thread.start()
        try:
            self.assertIsNone(self._probe(timeout=0.50))
        finally:
            thread.join(timeout=2.0)
            if thread.is_alive():
                self.fail("writer release thread did not finish")

    def test_persistent_writer_contention_fails_closed_specifically(self) -> None:
        writer = sqlite3.connect(self.db_path, timeout=0.0)
        try:
            writer.execute("BEGIN EXCLUSIVE")
            self.assertEqual(
                self._probe(timeout=0.05),
                "CANCELLATION_PROBE_SQLITE_LOCKED",
            )
        finally:
            writer.rollback()
            writer.close()

    def test_stopping_preserves_stored_reason(self) -> None:
        self._set_state("STOPPING", "OPERATOR_STOP")
        self.assertEqual(self._probe(), "OPERATOR_STOP")

    def test_terminal_state_remains_fail_closed(self) -> None:
        self._set_state("TERMINAL")
        self.assertEqual(self._probe(), "CAMPAIGN_SUPERVISION_TERMINAL")

    def test_missing_supervision_remains_fail_closed(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "DELETE FROM printer_memory_factory_campaign_supervision"
            )
            connection.commit()
        finally:
            connection.close()
        self.assertEqual(self._probe(), "CAMPAIGN_SUPERVISION_MISSING")

    def test_non_lock_sqlite_error_is_not_reclassified(self) -> None:
        connection = sqlite3.connect(self.db_path)
        try:
            connection.execute(
                "DROP TABLE printer_memory_factory_campaign_supervision"
            )
            connection.commit()
        finally:
            connection.close()
        with self.assertRaisesRegex(sqlite3.OperationalError, "no such table"):
            self._probe()


if __name__ == "__main__":
    unittest.main()
