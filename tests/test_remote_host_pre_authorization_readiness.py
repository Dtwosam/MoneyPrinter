from pathlib import Path
import tempfile
import unittest

from printer_v1.operator_cli.linux_remote_host_portability import (
    LinuxPortabilityError,
    assert_remote_disk_space,
    assert_system_time_synchronized,
)


class _DiskUsage:
    def __init__(self, *, total: int, free: int):
        self.total = total
        self.used = total - free
        self.free = free


class _Result:
    def __init__(self, *, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


class RemoteDiskSpaceReadinessTests(unittest.TestCase):
    def test_required_space_is_derived_from_db_size_and_existing_storage_ceiling(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "data" / "printer.sqlite3"
            db.parent.mkdir()
            db.write_bytes(b"0123456789")
            calls = []

            def disk_usage(path):
                calls.append(Path(path))
                return _DiskUsage(total=1_000, free=300)

            evidence = assert_remote_disk_space(
                authoritative_db_path=db,
                write_paths={
                    "database_parent": db.parent,
                    "artifact_root": root / "artifacts",
                },
                storage_growth_ceiling_bytes=100,
                disk_usage=disk_usage,
            )

            self.assertEqual(evidence["database_size_bytes"], 10)
            self.assertEqual(evidence["storage_growth_ceiling_bytes"], 100)
            self.assertEqual(evidence["required_free_bytes"], 230)
            self.assertEqual(len(calls), 2)
            self.assertTrue(evidence["paths"]["artifact_root"]["approved"])

    def test_insufficient_space_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            db = root / "printer.sqlite3"
            db.write_bytes(b"0123456789")

            with self.assertRaises(LinuxPortabilityError):
                assert_remote_disk_space(
                    authoritative_db_path=db,
                    write_paths={"artifact_root": root / "artifacts"},
                    storage_growth_ceiling_bytes=100,
                    disk_usage=lambda _path: _DiskUsage(total=1_000, free=200),
                )


class SystemTimeReadinessTests(unittest.TestCase):
    def test_synchronized_systemd_clock_passes(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return _Result(stdout="yes\n")

        evidence = assert_system_time_synchronized(runner=runner)

        self.assertTrue(evidence["ntp_synchronized"])
        self.assertEqual(
            calls[0][0],
            ["timedatectl", "show", "--property=NTPSynchronized", "--value"],
        )
        self.assertFalse(calls[0][1]["shell"])
        self.assertGreater(calls[0][1]["timeout"], 0)

    def test_unsynchronized_or_uninspectable_clock_blocks(self):
        with self.assertRaises(LinuxPortabilityError):
            assert_system_time_synchronized(
                runner=lambda _command, **_kwargs: _Result(stdout="no\n")
            )
        with self.assertRaises(LinuxPortabilityError):
            assert_system_time_synchronized(
                runner=lambda _command, **_kwargs: _Result(
                    stdout="", returncode=1
                )
            )


if __name__ == "__main__":
    unittest.main()
