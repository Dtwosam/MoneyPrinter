from pathlib import Path
import signal
import sqlite3
import subprocess
import tempfile
import unittest

from printer_v1.operator_cli.linux_remote_host_portability import (
    LinuxPortabilityError,
    StopSignalState,
    assert_local_ext4_paths,
    attempt_exact_active_cancellation,
    fsync_directory_required,
    launch_child_foreground,
    parse_mountinfo,
    resolve_exact_active_supervision,
)


EXT4_MOUNTINFO = r'''36 25 0:32 / / rw,relatime - ext4 /dev/vda1 rw
41 36 0:40 /srv/printer /srv/printer rw,relatime - ext4 /dev/vdb1 rw
'''


class LinuxFilesystemPreflightTests(unittest.TestCase):
    def test_longest_mount_match_accepts_local_ext4(self):
        entries = parse_mountinfo(EXT4_MOUNTINFO)
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            evidence = assert_local_ext4_paths(
                {"db": root / "data" / "printer.sqlite3"},
                mountinfo_text=(
                    f"36 25 0:32 / {root} rw,relatime - ext4 /dev/vda1 rw\n"
                ),
            )
        self.assertEqual(evidence["db"]["filesystem_type"], "ext4")
        self.assertEqual(entries[1].filesystem_type, "ext4")

    def test_network_or_unknown_filesystem_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            with self.assertRaises(LinuxPortabilityError):
                assert_local_ext4_paths(
                    {"db": root / "data" / "printer.sqlite3"},
                    mountinfo_text=(
                        f"36 25 0:32 / {root} rw,relatime - nfs4 server:/printer rw\n"
                    ),
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

    def _insert_active(self, path: Path, *, suffix: str = "1") -> None:
        conn = sqlite3.connect(path)
        conn.execute(
            '''INSERT INTO printer_memory_factory_campaign_supervision(
                supervision_id,campaign_id,configuration_id,run_id,owner_id,
                supervision_state,created_at
            ) VALUES (?,?,?,?,?,'ACTIVE',?)''',
            (
                f"sup-{suffix}",
                f"camp-{suffix}",
                f"cfg-{suffix}",
                f"run-{suffix}",
                f"owner-{suffix}",
                "2999-01-01T00:00:00+00:00",
            ),
        )
        conn.commit()
        conn.close()

    def test_zero_rows_is_not_ready_and_unique_current_row_resolves(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            self.assertIsNone(
                resolve_exact_active_supervision(
                    path, child_started_at="2026-08-27T18:00:00+00:00"
                )
            )
            self._insert_active(path)
            row = resolve_exact_active_supervision(
                path, child_started_at="2026-08-27T18:00:00+00:00"
            )
            self.assertEqual(row["supervision_id"], "sup-1")

    def test_multiple_active_rows_fail_closed(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            self._insert_active(path, suffix="1")
            self._insert_active(path, suffix="2")
            with self.assertRaises(LinuxPortabilityError):
                resolve_exact_active_supervision(
                    path, child_started_at="2026-08-27T18:00:00+00:00"
                )


class CooperativeStopBridgeTests(ExactSupervisionTests):
    def test_exact_cancellation_is_requested_once(self):
        with tempfile.TemporaryDirectory() as td:
            path = self._database(Path(td))
            self._insert_active(path)
            state = StopSignalState()
            state.handle_signal(signal.SIGTERM, None)
            calls = []

            def requester(db_path, **kwargs):
                calls.append((Path(db_path), kwargs))
                return {"cancellation_requested": True}

            first = attempt_exact_active_cancellation(
                path,
                stop_state=state,
                child_started_at="2026-08-27T18:00:00+00:00",
                requester=requester,
            )
            second = attempt_exact_active_cancellation(
                path,
                stop_state=state,
                child_started_at="2026-08-27T18:00:00+00:00",
                requester=requester,
            )
            self.assertTrue(first)
            self.assertFalse(second)
            self.assertEqual(len(calls), 1)
            self.assertEqual(calls[0][1]["supervision_id"], "sup-1")

    def test_foreground_launcher_never_direct_signals_child(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = root / "app"
            app.mkdir()
            stdout = app / "child-stdout.txt"
            stderr = app / "child-stderr.txt"
            path = self._database(root)
            state = StopSignalState()
            cancellation_calls = []

            class FakeProcess:
                pid = 4242
                waits = 0

                def wait(self, timeout=None):
                    self.waits += 1
                    if self.waits == 1:
                        state.handle_signal(signal.SIGTERM, None)
                        self_outer._insert_active(path)
                        raise subprocess.TimeoutExpired(["child"], timeout)
                    return 0

            self_outer = self
            process = FakeProcess()

            def popen_factory(*args, **kwargs):
                return process

            def requester(db_path, **kwargs):
                cancellation_calls.append(kwargs)
                return {"cancellation_requested": True}

            launched = launch_child_foreground(
                command=["child"],
                cwd=root,
                env={},
                stdout_path=stdout,
                stderr_path=stderr,
                authoritative_db_path=path,
                stop_state=state,
                popen_factory=popen_factory,
                cancellation_requester=requester,
                wait_timeout_seconds=0.01,
                directory_sync=lambda _path: None,
            )
            self.assertEqual(launched["returncode"], 0)
            self.assertEqual(launched["pid"], 4242)
            self.assertEqual(len(cancellation_calls), 1)
            self.assertTrue(state.cancellation_attempted)


class SystemdArtifactTests(unittest.TestCase):
    def test_service_has_manual_one_shot_safety_contract(self):
        service = (
            Path(__file__).resolve().parents[1]
            / "deploy"
            / "systemd"
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
