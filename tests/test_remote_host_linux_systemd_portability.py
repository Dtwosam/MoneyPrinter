import os
from pathlib import Path
import sqlite3
import signal
import tempfile
import unittest

from printer_v1.operator_cli.linux_remote_host_portability import (
    LinuxPortabilityError,
    StopSignalState,
    assert_local_ext4_paths,
    fsync_directory_required,
    parse_mountinfo,
    resolve_exact_active_supervision,
)


EXT4_MOUNTINFO = r'''36 25 0:32 / / rw,relatime - ext4 /dev/vda1 rw
41 36 0:40 /srv/printer /srv/printer rw,relatime - ext4 /dev/vdb1 rw
'''
REMOTE_MOUNTINFO = r'''36 25 0:32 / / rw,relatime - ext4 /dev/vda1 rw
41 36 0:40 / /srv/printer rw,relatime - nfs4 server:/printer rw
'''


class LinuxFilesystemPreflightTests(unittest.TestCase):
    def test_longest_mount_match_accepts_local_ext4(self):
        entries = parse_mountinfo(EXT4_MOUNTINFO)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = assert_local_ext4_paths(
                {"db": root / "data" / "printer.sqlite3"},
                mountinfo_text=f"36 25 0:32 / {root} rw,relatime - ext4 /dev/vda1 rw\n",
            )
        self.assertEqual(evidence["db"]["filesystem_type"], "ext4")
        self.assertEqual(entries[1].filesystem_type, "ext4")

    def test_network_or_unknown_filesystem_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(LinuxPortabilityError):
                assert_local_ext4_paths(
                    {"db": root / "data" / "printer.sqlite3"},
                    mountinfo_text=f"36 25 0:32 / {root} rw,relatime - nfs4 server:/printer rw\n",
                )
        with self.assertRaises(LinuxPortabilityError):
            parse_mountinfo("malformed mountinfo\n")


class DirectoryDurabilityTests(unittest.TestCase):
    def test_directory_fsync_success_and_symlink_rejection(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            real = root / "real"
            real.mkdir()
            fsync_directory_required(real)
            alias = root / "alias"
            try:
                alias.symlink_to(real, target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unsupported")
            with self.assertRaises(LinuxPortabilityError):
                fsync_directory_required(alias)


class StopSignalTests(unittest.TestCase):
    def test_signal_handler_is_process_local_and_idempotent(self):
        state = StopSignalState()
        state.handle_signal(signal.SIGTERM, None)
        state.handle_signal(signal.SIGINT, None)
        self.assertTrue(state.requested)
        self.assertEqual(state.first_signal, signal.SIGTERM)
        self.assertEqual(state.signal_count, 2)
        self.assertFalse(state.cancellation_attempted)


class ExactSupervisionTests(unittest.TestCase):
    def _database(self, root: Path) -> Path:
        path = root / "supervision.sqlite3"
        conn = sqlite3.connect(path)
        conn.executescript(
            '''
            CREATE TABLE printer_memory_factory_campaign_supervision (
                supervision_id TEXT PRIMARY KEY,
                campaign_id TEXT NOT NULL,
                configuration_id TEXT NOT NULL,
                run_id TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                supervision_state TEXT NOT NULL,
                cancellation_requested_at TEXT,
                cancellation_reason TEXT,
                created_at TEXT NOT NULL
            );
            '''
        )
        conn.commit()
        conn.close()
        return path

    def test_zero_rows_is_not_ready_and_unique_current_row_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            self.assertIsNone(
                resolve_exact_active_supervision(
                    path, child_started_at="2026-08-27T18:00:00+00:00"
                )
            )
            conn = sqlite3.connect(path)
            conn.execute(
                '''INSERT INTO printer_memory_factory_campaign_supervision(
                    supervision_id,campaign_id,configuration_id,run_id,owner_id,
                    supervision_state,created_at
                ) VALUES (?,?,?,?,?,'ACTIVE',?)''',
                ("sup-1", "camp-1", "cfg-1", "run-1", "owner-1", "2026-08-27T18:00:01+00:00"),
            )
            conn.commit(); conn.close()
            row = resolve_exact_active_supervision(
                path, child_started_at="2026-08-27T18:00:00+00:00"
            )
            self.assertEqual(row["supervision_id"], "sup-1")

    def test_multiple_or_stale_active_rows_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            conn = sqlite3.connect(path)
            for i, created in ((1, "2026-08-27T18:00:01+00:00"), (2, "2026-08-27T18:00:02+00:00")):
                conn.execute(
                    '''INSERT INTO printer_memory_factory_campaign_supervision(
                        supervision_id,campaign_id,configuration_id,run_id,owner_id,
                        supervision_state,created_at
                    ) VALUES (?,?,?,?,?,'ACTIVE',?)''',
                    (f"sup-{i}", f"camp-{i}", f"cfg-{i}", f"run-{i}", f"owner-{i}", created),
                )
            conn.commit(); conn.close()
            with self.assertRaises(LinuxPortabilityError):
                resolve_exact_active_supervision(
                    path, child_started_at="2026-08-27T18:00:00+00:00"
                )


class SystemdArtifactTests(unittest.TestCase):
    def test_service_has_manual_one_shot_safety_contract(self):
        service = (
            Path(__file__).resolve().parents[1]
            / "deploy" / "systemd"
            / "printer-v1-four-token-standard-four-hour.service"
        )
        text = service.read_text(encoding="utf-8")
        self.assertIn("Type=exec", text)
        self.assertIn("Restart=no", text)
        self.assertIn("RemainAfterExit=no", text)
        self.assertIn("KillMode=mixed", text)
        self.assertIn("UMask=0077", text)
        self.assertIn("four_token_standard_four_hour_linux_service", text)
        self.assertNotIn("operational_memory_factory_command", text)
        self.assertNotIn("WantedBy=", text)
        self.assertNotIn("WatchdogSec=", text)
        self.assertNotIn("ExecStartPre=", text)
        self.assertNotIn("ExecStopPost=", text)


if __name__ == "__main__":
    unittest.main()
