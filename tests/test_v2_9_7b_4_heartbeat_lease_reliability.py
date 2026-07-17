"""V2-9.7B.4 heartbeat lease and launcher-fault reliability tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
from unittest import mock
import shutil
import subprocess
import unittest
import uuid

from printer_v1.operator_cli import proof_supervision
from printer_v1.operator_cli.proof_supervision import (
    LEASE_REPLACE_MAX_ATTEMPTS,
    PROOF_SCOPE,
    ProofSupervisionError,
    heartbeat_active_lease,
)


ROOT = Path(__file__).resolve().parents[1]
LOGGING_MODULE = ROOT / "scripts" / "V2-9-LauncherLogging.ps1"
LAUNCHER = ROOT / "scripts" / "Start-V2-9-Proof.ps1"
PERSISTENT_DB = ROOT / "data" / "printer_v1.sqlite3"
POWERSHELL = shutil.which("powershell.exe")
T0 = datetime(2026, 7, 17, 12, 0, tzinfo=timezone.utc)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _transient_replace_error() -> PermissionError:
    error = PermissionError("Access is denied during atomic replacement")
    error.winerror = 5
    return error


class HeartbeatLeaseReliabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = ROOT
        self.prefix = f".v2-9-7b-4-{uuid.uuid4().hex}"
        self.lock = self.root / f"{self.prefix}-one-proof.lock.json"
        self.execution_id = "execution-v2-9-7b-4"
        self.payload = {
            "proof_scope": PROOF_SCOPE,
            "execution_id": self.execution_id,
            "proof_db_path": str(self.root / "proof.sqlite3"),
            "process_id": 424242,
            "heartbeat_at": T0.isoformat(),
            "lease_expires_at": (T0 + timedelta(seconds=90)).isoformat(),
            "created_at": T0.isoformat(),
            "updated_at": T0.isoformat(),
        }
        self.lock.write_text(
            json.dumps(self.payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        for path in self.root.glob(f"{self.prefix}*"):
            path.unlink(missing_ok=True)
        for path in self.root.glob(f".{self.lock.name}.*.tmp"):
            path.unlink(missing_ok=True)

    def _temp_files(self) -> list[Path]:
        return list(self.root.glob(f".{self.lock.name}.*.tmp"))

    def test_repeated_renewals_are_owned_monotonic_valid_and_temp_free(self) -> None:
        previous = self.payload
        for seconds in (30, 60, 89):
            renewed = heartbeat_active_lease(
                self.lock,
                self.execution_id,
                process_id=424242,
                lease_seconds=90,
                now=T0 + timedelta(seconds=seconds),
            )
            persisted = json.loads(self.lock.read_text(encoding="utf-8"))
            self.assertEqual(persisted["execution_id"], self.execution_id)
            self.assertEqual(persisted["proof_scope"], PROOF_SCOPE)
            self.assertGreater(
                datetime.fromisoformat(persisted["heartbeat_at"]),
                datetime.fromisoformat(previous["heartbeat_at"]),
            )
            self.assertGreater(
                datetime.fromisoformat(persisted["lease_expires_at"]),
                datetime.fromisoformat(previous["lease_expires_at"]),
            )
            self.assertEqual(renewed["lease_replace_attempts"], 1)
            self.assertEqual(renewed["lease_replace_retries"], 0)
            self.assertEqual(self._temp_files(), [])
            previous = persisted

    def test_transient_windows_replacement_retries_bounded_and_reports_success(self) -> None:
        real_replace = os.replace
        attempts = 0

        def flaky_replace(source: str | bytes, target: str | bytes) -> None:
            nonlocal attempts
            attempts += 1
            if attempts < LEASE_REPLACE_MAX_ATTEMPTS:
                raise _transient_replace_error()
            real_replace(source, target)

        with (
            mock.patch.object(proof_supervision.os, "replace", side_effect=flaky_replace),
            mock.patch.object(proof_supervision.time, "sleep") as sleep,
        ):
            renewed = heartbeat_active_lease(
                self.lock,
                self.execution_id,
                now=T0 + timedelta(seconds=30),
            )

        self.assertEqual(attempts, LEASE_REPLACE_MAX_ATTEMPTS)
        self.assertEqual(
            renewed["lease_replace_attempts"], LEASE_REPLACE_MAX_ATTEMPTS
        )
        self.assertEqual(
            renewed["lease_replace_retries"], LEASE_REPLACE_MAX_ATTEMPTS - 1
        )
        self.assertEqual(sleep.call_count, LEASE_REPLACE_MAX_ATTEMPTS - 1)
        self.assertEqual(self._temp_files(), [])
        self.assertEqual(
            json.loads(self.lock.read_text(encoding="utf-8"))["heartbeat_at"],
            (T0 + timedelta(seconds=30)).isoformat(),
        )

    def test_permanent_replacement_failure_never_claims_renewal(self) -> None:
        before = self.lock.read_bytes()
        with (
            mock.patch.object(
                proof_supervision.os,
                "replace",
                side_effect=_transient_replace_error(),
            ) as replace,
            mock.patch.object(proof_supervision.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(
                ProofSupervisionError,
                rf"after {LEASE_REPLACE_MAX_ATTEMPTS} attempt",
            ):
                heartbeat_active_lease(
                    self.lock,
                    self.execution_id,
                    now=T0 + timedelta(seconds=30),
                )
        self.assertEqual(replace.call_count, LEASE_REPLACE_MAX_ATTEMPTS)
        self.assertEqual(sleep.call_count, LEASE_REPLACE_MAX_ATTEMPTS - 1)
        self.assertEqual(self.lock.read_bytes(), before)
        self.assertEqual(self._temp_files(), [])

    def test_missing_foreign_expired_and_malformed_locks_fail_closed(self) -> None:
        cases: list[tuple[str, object, str]] = [
            ("missing", None, "different execution"),
            (
                "foreign",
                {**self.payload, "execution_id": "foreign"},
                "different execution",
            ),
            (
                "expired",
                {
                    **self.payload,
                    "lease_expires_at": (T0 + timedelta(seconds=10)).isoformat(),
                },
                "expired",
            ),
            (
                "malformed-timestamp",
                {**self.payload, "heartbeat_at": "not-a-time"},
                "timestamps are malformed",
            ),
            ("malformed-json", "{not-json", "ambiguous one-proof lock"),
        ]
        for name, value, message in cases:
            with self.subTest(name=name):
                if value is None:
                    self.lock.unlink(missing_ok=True)
                elif isinstance(value, str):
                    self.lock.write_text(value, encoding="utf-8")
                else:
                    self.lock.write_text(json.dumps(value), encoding="utf-8")
                with self.assertRaisesRegex(ProofSupervisionError, message):
                    heartbeat_active_lease(
                        self.lock,
                        self.execution_id,
                        now=T0 + timedelta(seconds=30),
                    )
                self.assertEqual(self._temp_files(), [])
                self.lock.write_text(json.dumps(self.payload), encoding="utf-8")

    def test_non_transient_replace_error_is_not_retried(self) -> None:
        with (
            mock.patch.object(
                proof_supervision.os,
                "replace",
                side_effect=OSError("not a Windows sharing error"),
            ) as replace,
            mock.patch.object(proof_supervision.time, "sleep") as sleep,
        ):
            with self.assertRaisesRegex(ProofSupervisionError, "after 1 attempt"):
                heartbeat_active_lease(
                    self.lock,
                    self.execution_id,
                    now=T0 + timedelta(seconds=30),
                )
        self.assertEqual(replace.call_count, 1)
        sleep.assert_not_called()
        self.assertEqual(self._temp_files(), [])


@unittest.skipUnless(POWERSHELL, "Windows PowerShell 5.1 is required")
class LauncherFaultObservabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.persistent_hash = _sha256(PERSISTENT_DB)

    def setUp(self) -> None:
        self.root = ROOT
        self.prefix = f".v2-9-7b-4-launcher-{uuid.uuid4().hex}"
        self.lock = self.root / f"{self.prefix}-one-proof.lock.json"
        self.log = self.root / f"{self.prefix}-launcher.jsonl"
        self.fallback = self.root / f"{self.prefix}-launcher-fallback.log"
        now = datetime.now(timezone.utc)
        payload = {
            "proof_scope": PROOF_SCOPE,
            "execution_id": "launcher-execution",
            "proof_db_path": str(self.root / "proof.sqlite3"),
            "process_id": 424242,
            "heartbeat_at": (now - timedelta(seconds=30)).isoformat(),
            "lease_expires_at": (now + timedelta(seconds=30)).isoformat(),
            "created_at": T0.isoformat(),
            "updated_at": (now - timedelta(seconds=30)).isoformat(),
        }
        self.lock.write_text(json.dumps(payload), encoding="utf-8")

    def tearDown(self) -> None:
        self.assertEqual(_sha256(PERSISTENT_DB), self.persistent_hash)
        for path in self.root.glob(f"{self.prefix}*"):
            path.unlink(missing_ok=True)
        for path in self.root.glob(f".{self.lock.name}.*.tmp"):
            path.unlink(missing_ok=True)

    def _run(self, body: str) -> subprocess.CompletedProcess[str]:
        script = self.root / f"{self.prefix}-harness.ps1"
        script.write_text(
            "$ErrorActionPreference = 'Stop'\n"
            "Set-StrictMode -Version Latest\n"
            f". '{LOGGING_MODULE}'\n"
            "Initialize-LauncherLogging "
            f"-LauncherLogPath '{self.log}' "
            f"-FallbackLogPath '{self.fallback}' "
            "-ExecutionId 'launcher-execution' -AttemptNumber 7\n"
            + body,
            encoding="utf-8",
        )
        return subprocess.run(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-NonInteractive",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                str(script),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=30,
            check=False,
        )

    def test_confirmed_renewal_survives_unreadable_output_and_future_heartbeat(self) -> None:
        python = shutil.which("python")
        self.assertIsNotNone(python)
        before = json.loads(self.lock.read_text(encoding="utf-8"))["heartbeat_at"]
        body = (
            "$badRenderer = { param($Value) "
            "throw [System.IO.IOException]::new('Stream was not readable.') }\n"
            f"$first = Invoke-SupervisionCommand -PythonPath '{python}' "
            "-Arguments @('heartbeat','--lock-path',"
            f"'{self.lock}','--execution-id','launcher-execution',"
            "'--lease-seconds','90') -OutputRenderer $badRenderer\n"
            "if (-not $first.CommandSucceeded) { throw 'first renewal was not confirmed' }\n"
            "Start-Sleep -Milliseconds 100\n"
            f"$second = Invoke-SupervisionCommand -PythonPath '{python}' "
            "-Arguments @('heartbeat','--lock-path',"
            f"'{self.lock}','--execution-id','launcher-execution',"
            "'--lease-seconds','90')\n"
            "if (-not $second.CommandSucceeded) { throw 'future renewal stopped' }\n"
            "$fault = Get-LauncherLogFirstFault\n"
            "if ($null -eq $fault) { throw 'fault was not retained' }\n"
            "\"BOUNDARY=$($fault.boundary)\"\n"
            "'LEASE_CONTINUITY_OK'\n"
        )
        result = self._run(body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("LEASE_CONTINUITY_OK", result.stdout)
        self.assertIn(
            "BOUNDARY=Invoke-Supervision:output:heartbeat",
            result.stdout,
        )
        after = json.loads(self.lock.read_text(encoding="utf-8"))["heartbeat_at"]
        self.assertGreater(datetime.fromisoformat(after), datetime.fromisoformat(before))
        fallback_text = self.fallback.read_text(encoding="utf-8-sig")
        self.assertIn("Stream was not readable.", fallback_text)

    def test_launcher_contract_stops_after_exhausted_renewal_without_restart(self) -> None:
        launcher = LAUNCHER.read_text(encoding="utf-8")
        self.assertIn(
            "One unconfirmed renewal therefore starts fail-closed shutdown.",
            launcher,
        )
        self.assertNotIn("$heartbeatFailures -ge 2", launcher)
        self.assertIn("if ($null -eq $launcherFaultReason)", launcher)
        self.assertEqual(launcher.count("Start-Process"), 1)
        self.assertIn("automatic_retries = 0", launcher)
        self.assertNotIn("Restart-Process", launcher)
        self.assertNotIn("successor", launcher.lower())


if __name__ == "__main__":
    unittest.main()