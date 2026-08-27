from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

from printer_v1.operator_cli import linux_remote_host_native_preflight as native


class _Result:
    def __init__(self, *, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


class NativeHostRuntimePreflightTests(unittest.TestCase):
    def test_fixture_runtime_records_exact_linux_host_identity(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            python_path = root / ".venv" / "bin" / "python"
            python_path.parent.mkdir(parents=True)
            python_path.write_text("#!/bin/sh\n")
            sizing_db = root / "sizing.sqlite3"
            sizing_db.write_bytes(b"db")
            calls = []

            outputs = {
                ("git", "--version"): "git version 2.47.3\n",
                ("git", "-C", str(root.resolve()), "rev-parse", "HEAD"): (
                    "a" * 40 + "\n"
                ),
                (
                    "git",
                    "-C",
                    str(root.resolve()),
                    "rev-parse",
                    "--abbrev-ref",
                    "HEAD",
                ): "agent/remote-host-linux-portability-implementation\n",
                ("ps", "--version"): "ps from procps-ng 4.0.4\n",
                ("systemd-analyze", "--version"): "systemd 257\n",
            }

            def runner(command, **kwargs):
                calls.append((tuple(command), kwargs))
                if tuple(command[:2]) == ("systemd-analyze", "verify"):
                    return _Result()
                return _Result(stdout=outputs[tuple(command)])

            evidence = native.collect_native_host_preflight(
                repository_root=root,
                sizing_db_path=sizing_db,
                application_root=root / "applications",
                artifact_root=root / "artifacts",
                systemd_unit=root / "service.unit",
                storage_growth_ceiling_bytes=100,
                python_version_info=(3, 11, 9),
                python_executable=python_path,
                sqlite_version="3.46.1",
                openssl_version="OpenSSL 3.5.5",
                package_version=lambda name: {
                    "websockets": "16.0",
                    "certifi": "2026.5.20",
                }[name],
                runner=runner,
                filesystem_preflight=lambda paths: {
                    key: {"approved": True, "filesystem_type": "ext4"}
                    for key in paths
                },
                disk_space_preflight=lambda **kwargs: {
                    "required_free_bytes": 123,
                    "paths": {},
                },
                time_sync_preflight=lambda **kwargs: {
                    "ntp_synchronized": True,
                    "approved": True,
                },
                service_account_preflight=lambda **kwargs: {
                    "user": "printer-v1",
                    "approved": True,
                },
            )

            self.assertEqual(evidence["runtime"]["python_version"], "3.11.9")
            self.assertEqual(evidence["runtime"]["websockets_version"], "16.0")
            self.assertEqual(evidence["git"]["head"], "a" * 40)
            self.assertEqual(evidence["procps"]["version"], "ps from procps-ng 4.0.4")
            self.assertTrue(evidence["systemd"]["unit_verified"])
            self.assertTrue(evidence["time_sync"]["ntp_synchronized"])
            self.assertTrue(all(not kwargs["shell"] for _, kwargs in calls))

    def test_non_python_311_blocks_before_command_probes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            calls = []
            with self.assertRaises(native.NativeHostPreflightError):
                native.collect_native_host_preflight(
                    repository_root=root,
                    sizing_db_path=root / "sizing.sqlite3",
                    application_root=root / "applications",
                    artifact_root=root / "artifacts",
                    systemd_unit=root / "service.unit",
                    storage_growth_ceiling_bytes=100,
                    python_version_info=(3, 13, 5),
                    python_executable=root / ".venv" / "bin" / "python",
                    runner=lambda command, **kwargs: calls.append(command),
                )
            self.assertEqual(calls, [])

    def test_systemd_unit_verification_failure_blocks(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            python_path = root / ".venv" / "bin" / "python"
            python_path.parent.mkdir(parents=True)
            python_path.write_text("#!/bin/sh\n")
            sizing_db = root / "sizing.sqlite3"
            sizing_db.write_bytes(b"db")

            def runner(command, **kwargs):
                command = tuple(command)
                if command[:2] == ("systemd-analyze", "verify"):
                    return _Result(returncode=1, stderr="invalid unit")
                if command == ("git", "--version"):
                    return _Result(stdout="git version 2.47.3\n")
                if command[-2:] == ("rev-parse", "HEAD"):
                    return _Result(stdout="a" * 40 + "\n")
                if command[-3:] == ("rev-parse", "--abbrev-ref", "HEAD"):
                    return _Result(stdout="branch\n")
                if command == ("ps", "--version"):
                    return _Result(stdout="ps from procps-ng 4.0.4\n")
                if command == ("systemd-analyze", "--version"):
                    return _Result(stdout="systemd 257\n")
                raise AssertionError(command)

            with self.assertRaises(native.NativeHostPreflightError):
                native.collect_native_host_preflight(
                    repository_root=root,
                    sizing_db_path=sizing_db,
                    application_root=root / "applications",
                    artifact_root=root / "artifacts",
                    systemd_unit=root / "service.unit",
                    storage_growth_ceiling_bytes=100,
                    python_version_info=(3, 11, 9),
                    python_executable=python_path,
                    sqlite_version="3.46.1",
                    openssl_version="OpenSSL 3.5.5",
                    package_version=lambda name: "fixture",
                    runner=runner,
                    filesystem_preflight=lambda paths: {},
                    disk_space_preflight=lambda **kwargs: {},
                    time_sync_preflight=lambda **kwargs: {},
                    service_account_preflight=lambda **kwargs: {},
                )


if __name__ == "__main__":
    unittest.main()
