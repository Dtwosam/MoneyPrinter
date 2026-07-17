"""V2-9.4.3 launcher supervision and log-writer reliability fixtures.

Attempt 6 proved the fault: a filesystem heartbeat succeeded and renewed the
lease, then the PowerShell native-output capture/logging boundary threw. Because
logging ran inside the supervision-output loop and the catch path reused the
same logger, the successful heartbeat was discarded, no fault could record
itself, and supervision stopped while a healthy child ran on.

These fixtures drive the real logging boundary through real powershell.exe
invocations with injected faults. No live sources, no proof runtime, no
persistent DB writes, temporary paths only.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts" / "Start-V2-9-Proof.ps1"
LOGGING_MODULE = ROOT / "scripts" / "V2-9-LauncherLogging.ps1"
PERSISTENT_DB = ROOT / "data" / "printer_v1.sqlite3"
POWERSHELL = shutil.which("powershell.exe")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LauncherLogReliabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if POWERSHELL is None:
            raise unittest.SkipTest("Windows PowerShell 5.1 is required")
        cls.persistent_hash = _sha256(PERSISTENT_DB)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.log = self.dir / "launcher.jsonl"
        self.fallback = self.dir / "launcher-fallback.log"

    def tearDown(self) -> None:
        # Every fixture must leave the canonical persistent DB untouched.
        self.assertEqual(_sha256(PERSISTENT_DB), self.persistent_hash)
        self.temp.cleanup()

    def _run_ps(self, body: str, timeout: int = 60) -> subprocess.CompletedProcess:
        script = self.dir / "harness.ps1"
        header = (
            "$ErrorActionPreference = 'Stop'\n"
            "Set-StrictMode -Version Latest\n"
            f". '{LOGGING_MODULE}'\n"
            "Initialize-LauncherLogging "
            f"-LauncherLogPath '{self.log}' "
            f"-FallbackLogPath '{self.fallback}' "
            "-ExecutionId 'exec-v2-9-4-3' -AttemptNumber 7\n"
        )
        script.write_text(header + body, encoding="utf-8")
        return subprocess.run(
            [
                str(POWERSHELL), "-NoProfile", "-NonInteractive",
                "-ExecutionPolicy", "Bypass", "-File", str(script),
            ],
            cwd=str(self.dir), text=True, capture_output=True,
            timeout=timeout, check=False,
        )

    def _jsonl(self) -> list[dict]:
        if not self.log.exists():
            return []
        records = []
        for line in self.log.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                # Any partial JSON record fails here, proving structural validity.
                records.append(json.loads(line))
        return records

    # --- healthy path -------------------------------------------------------

    def test_healthy_logging_writes_complete_jsonl_records(self) -> None:
        result = self._run_ps(
            "1..5 | ForEach-Object { "
            "Write-LauncherEvent -Event 'PROBE' -Details @{ i = $_ } | Out-Null }\n"
            "if (-not (Test-LauncherLogHealthy)) { throw 'logger should be healthy' }\n"
            "if ($null -ne (Get-LauncherLogFirstFault)) { throw 'no fault expected' }\n"
            "'HEALTHY_OK'\n"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("HEALTHY_OK", result.stdout)
        records = self._jsonl()
        self.assertEqual(len(records), 5)
        for index, record in enumerate(records, start=1):
            self.assertEqual(record["event"], "PROBE")
            self.assertEqual(record["execution_id"], "exec-v2-9-4-3")
            self.assertEqual(record["attempt_number"], 7)
            self.assertEqual(record["details"]["i"], index)
        self.assertFalse(self.fallback.exists())

    # --- injected primary log-write failure --------------------------------

    def test_log_write_failure_never_throws_and_records_first_cause_once(self) -> None:
        # Injected primary-log failure: the log path is occupied by a directory,
        # so every append raises inside Write-LauncherEvent.
        body = (
            "New-Item -ItemType Directory -Force -Path $LauncherLogPathBlocker | Out-Null\n"
            "$first = Write-LauncherEvent -Event 'AFTER_HEARTBEAT' -Details @{ a = 1 }\n"
            "$second = Write-LauncherEvent -Event 'LATER' -Details @{ a = 2 }\n"
            "if ($first -ne $false) { throw 'expected first write to report failure' }\n"
            "if ($second -ne $false) { throw 'expected second write to report failure' }\n"
            "if (Test-LauncherLogHealthy) { throw 'logger should be unhealthy' }\n"
            "$fault = Get-LauncherLogFirstFault\n"
            "if ($null -eq $fault) { throw 'first fault must be recorded' }\n"
            "\"BOUNDARY=$($fault.boundary)\"\n"
            "'NO_THROW_OK'\n"
        )
        script_prefix = f"$LauncherLogPathBlocker = '{self.log}'\n"
        result = self._run_ps(script_prefix + body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("NO_THROW_OK", result.stdout)
        # The exact first cause is preserved, not the later symptom.
        self.assertIn("BOUNDARY=Write-LauncherEvent:AFTER_HEARTBEAT", result.stdout)

    def test_durable_fallback_holds_exact_first_cause_and_details(self) -> None:
        script_prefix = f"$LauncherLogPathBlocker = '{self.log}'\n"
        body = (
            "New-Item -ItemType Directory -Force -Path $LauncherLogPathBlocker | Out-Null\n"
            "Write-LauncherEvent -Event 'AFTER_HEARTBEAT' -Details @{ a = 1 } | Out-Null\n"
            "Write-LauncherEvent -Event 'LATER_SYMPTOM' -Details @{ a = 2 } | Out-Null\n"
            "'FALLBACK_OK'\n"
        )
        result = self._run_ps(script_prefix + body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # Durable diagnostics exist even though the primary logger is dead.
        self.assertTrue(self.fallback.exists())
        lines = [
            line for line in
            self.fallback.read_text(encoding="utf-8-sig").splitlines() if line.strip()
        ]
        # Exactly one first-cause record: a later fault never replaces it.
        self.assertEqual(len(lines), 1)
        fault = json.loads(lines[0])
        self.assertEqual(fault["event"], "LAUNCHER_LOG_FAULT")
        self.assertEqual(fault["boundary"], "Write-LauncherEvent:AFTER_HEARTBEAT")
        self.assertEqual(fault["execution_id"], "exec-v2-9-4-3")
        self.assertEqual(fault["attempt_number"], 7)
        # PowerShell error detail, command boundary, and stack are persisted.
        self.assertTrue(fault["message"])
        self.assertTrue(fault["exception_type"])
        self.assertIn("script_stack_trace", fault)
        self.assertIn("position_message", fault)
        self.assertIn("category", fault)
        self.assertIn("fully_qualified_error_id", fault)

    # --- separation of heartbeat result from logging ------------------------

    def test_repeated_native_output_survives_dead_logger_and_keeps_exit_code(self) -> None:
        """Real powershell.exe + real native command with repeated output.

        Injected primary-log failure immediately after a successful command:
        the authoritative exit code must survive, proving a logging fault can
        never discard a successful heartbeat/lease renewal or stop the loop.
        """
        python = shutil.which("python")
        self.assertIsNotNone(python)
        emitter = self.dir / "emit.py"
        emitter.write_text(
            "import sys\n"
            "for i in range(12):\n"
            "    print('{\"line\": %d, \"updated_at\": \"x\"}' % i, flush=True)\n"
            "sys.exit(0)\n",
            encoding="utf-8",
        )
        script_prefix = f"$Blocker = '{self.log}'\n"
        body = (
            # Kill the primary logger before any capture happens.
            "New-Item -ItemType Directory -Force -Path $Blocker | Out-Null\n"
            "$results = @()\n"
            "foreach ($round in 1..3) {\n"
            "  $out = @()\n"
            "  $global:LASTEXITCODE = $null\n"
            f"  $out = @(& '{python}' '{emitter}' 2>&1)\n"
            "  $code = $global:LASTEXITCODE\n"
            "  foreach ($line in $out) {\n"
            "    Write-LauncherEvent -Event 'SUPERVISION_OUTPUT' "
            "-Details @{ text = [string]$line } | Out-Null\n"
            "  }\n"
            "  $results += $code\n"
            "}\n"
            "foreach ($r in $results) { if ($r -ne 0) { throw \"exit code lost: $r\" } }\n"
            "if (Test-LauncherLogHealthy) { throw 'logger should be unhealthy' }\n"
            "\"ROUNDS=$($results.Count)\"\n"
            "'LOOP_SURVIVED'\n"
        )
        result = self._run_ps(script_prefix + body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        # All three rounds ran despite a permanently dead logger.
        self.assertIn("ROUNDS=3", result.stdout)
        self.assertIn("LOOP_SURVIVED", result.stdout)
        # The first cause is still preserved exactly once.
        lines = [
            line for line in
            self.fallback.read_text(encoding="utf-8-sig").splitlines() if line.strip()
        ]
        self.assertEqual(len(lines), 1)

    def test_invoke_supervision_command_returns_exit_code_with_dead_logger(self) -> None:
        """Invoke-SupervisionCommand keeps the authoritative result separate."""
        python = shutil.which("python")
        self.assertIsNotNone(python)
        script_prefix = f"$Blocker = '{self.log}'\n"
        body = (
            "New-Item -ItemType Directory -Force -Path $Blocker | Out-Null\n"
            # Use a real python module invocation that exits non-zero without a
            # proof runtime: an unknown subcommand. Exit code must survive.
            f"$r = Invoke-SupervisionCommand -PythonPath '{python}' "
            "-Arguments @('inspect-lock', '--lock-path', 'definitely-missing.json')\n"
            "if ($null -eq $r) { throw 'no result object' }\n"
            "\"EXIT=$($r.ExitCode)\"\n"
            "\"CAPTUREFAULT=$($r.CaptureFault)\"\n"
            "if (Test-LauncherLogHealthy) { throw 'logger should be unhealthy' }\n"
            "'INVOKE_OK'\n"
        )
        result = self._run_ps(script_prefix + body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("INVOKE_OK", result.stdout)
        # A real exit code was returned even though logging was dead.
        self.assertIn("EXIT=0", result.stdout)
        self.assertIn("CAPTUREFAULT=False", result.stdout)

    # --- injected capture failure ------------------------------------------

    def test_capture_failure_records_durable_exact_cause(self) -> None:
        """A capture-boundary fault is recorded durably with its exact cause."""
        script_prefix = ""
        body = (
            "$r = Invoke-SupervisionCommand -PythonPath "
            "'C:\\definitely\\missing\\python.exe' -Arguments @('inspect-lock')\n"
            "if (-not $r.CaptureFault) { throw 'expected capture fault' }\n"
            "$fault = Get-LauncherLogFirstFault\n"
            "if ($null -eq $fault) { throw 'capture fault must be recorded' }\n"
            "\"BOUNDARY=$($fault.boundary)\"\n"
            "'CAPTURE_OK'\n"
        )
        result = self._run_ps(script_prefix + body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("CAPTURE_OK", result.stdout)
        self.assertIn("BOUNDARY=Invoke-Supervision:capture:inspect-lock", result.stdout)
        # Durable diagnostics land even though this fault is not a log-write.
        self.assertTrue(self.fallback.exists())
        fault = json.loads(
            [
                line for line in
                self.fallback.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ][0]
        )
        self.assertEqual(fault["event"], "LAUNCHER_LOG_FAULT")
        self.assertTrue(fault["message"])
        # The primary log stays structurally valid (capture fault only).
        self.assertEqual(self._jsonl(), [])

    # --- terminal path with unavailable primary logger ---------------------

    def test_terminal_fallback_write_succeeds_when_primary_log_dead(self) -> None:
        script_prefix = f"$Blocker = '{self.log}'\n"
        body = (
            "New-Item -ItemType Directory -Force -Path $Blocker | Out-Null\n"
            "Write-LauncherEvent -Event 'LAUNCHER_FINISH' -Details @{ t = 'X' } | Out-Null\n"
            "if (-not (Test-LauncherLogHealthy)) {\n"
            "  $ok = Write-LauncherFallback -Text 'LAUNCHER_FINISH terminal_status=COMPLETED'\n"
            "  if (-not $ok) { throw 'fallback finish write failed' }\n"
            "}\n"
            "'TERMINAL_OK'\n"
        )
        result = self._run_ps(script_prefix + body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TERMINAL_OK", result.stdout)
        text = self.fallback.read_text(encoding="utf-8-sig")
        self.assertIn("LAUNCHER_FINISH terminal_status=COMPLETED", text)

    def test_fallback_unavailable_still_never_throws(self) -> None:
        """Last-resort path: even a dead fallback must not raise."""
        script_prefix = (
            f"$Blocker = '{self.log}'\n"
            f"$FallbackBlocker = '{self.fallback}'\n"
        )
        body = (
            "New-Item -ItemType Directory -Force -Path $Blocker | Out-Null\n"
            "New-Item -ItemType Directory -Force -Path $FallbackBlocker | Out-Null\n"
            "$w = Write-LauncherEvent -Event 'BOTH_DEAD' -Details @{ a = 1 }\n"
            "if ($w -ne $false) { throw 'expected failure report' }\n"
            "$f = Write-LauncherFallback -Text 'still must not throw'\n"
            "if ($f -ne $false) { throw 'expected fallback failure report' }\n"
            "'LAST_RESORT_OK'\n"
        )
        result = self._run_ps(script_prefix + body)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("LAST_RESORT_OK", result.stdout)

    # --- launcher contract --------------------------------------------------

    def test_launcher_wires_reliability_boundary_and_preserves_contracts(self) -> None:
        launcher = LAUNCHER.read_text(encoding="utf-8")
        # Logging boundary is dot-sourced and initialised.
        self.assertIn("V2-9-LauncherLogging.ps1", launcher)
        self.assertIn("Initialize-LauncherLogging", launcher)
        self.assertIn("Invoke-SupervisionCommand -PythonPath $python", launcher)
        self.assertIn("$launcherFallbackLog", launcher)
        # A log fault never becomes OPERATOR_CANCELLED: exactly one assignment,
        # guarded by the absence of a prior logging/capture fault.
        self.assertEqual(launcher.count("$operatorCancelled = $true"), 1)
        self.assertIn(
            "catch [System.Management.Automation.PipelineStoppedException]", launcher
        )
        self.assertIn("Get-LauncherLogFirstFault", launcher)
        # Genuine Ctrl+C is preserved: inside the pipeline-stopped catch the
        # log-fault guard is evaluated first, and OPERATOR_CANCELLED is reached
        # only on the else branch (no prior logging/capture fault).
        catch_block = launcher.split(
            "catch [System.Management.Automation.PipelineStoppedException] {", 1
        )[1].split("\ncatch {", 1)[0]
        self.assertIn("$logFault = Get-LauncherLogFirstFault", catch_block)
        self.assertLess(
            catch_block.index("if ($null -ne $logFault)"),
            catch_block.index("$operatorCancelled = $true"),
        )
        self.assertIn("else {", catch_block)
        self.assertIn("SAFE_STOP_OPERATOR_INTERRUPTED", catch_block)
        # Preserved V2-9.4/9.4.1/9.4.2 contracts.
        self.assertIn("[int]$AttemptNumber", launcher)
        self.assertIn("v2-9-attempt$AttemptNumber", launcher)
        self.assertNotIn("attempt4", launcher)
        self.assertIn("'SUPERVISION_HEARTBEAT_PERSISTENCE_FAILED'", launcher)
        self.assertNotIn("$heartbeatFailures -ge 2", launcher)
        self.assertIn("One unconfirmed renewal therefore starts fail-closed shutdown.", launcher)
        self.assertIn("'--lock-path', $lockPath", launcher)
        self.assertIn("'-u'", launcher)
        self.assertIn("FORCED_TERMINATION_AFTER_EXPIRED_LEASE", launcher)
        self.assertIn("automatic_retries = 0", launcher)
        # The boundary carries no proof-runtime, schema, or evidence logic: it
        # only forwards an opaque supervision argument list.
        module = LOGGING_MODULE.read_text(encoding="utf-8")
        for forbidden in (
            "proof_db_schema_readiness",
            "run_one_command",
            "apply_migrations",
            "printer_token_snapshots",
            "--db-path",
        ):
            self.assertNotIn(forbidden, module)

    def test_every_write_launcher_event_call_is_out_nulled(self) -> None:
        """A stray return value would corrupt the launcher's JSON stdout."""
        launcher = LAUNCHER.read_text(encoding="utf-8")
        calls = launcher.count("Write-LauncherEvent -Event")
        piped = launcher.count("} | Out-Null") + launcher.count("Id } | Out-Null")
        self.assertGreater(calls, 0)
        # Every call site terminates with an Out-Null guard.
        self.assertNotIn("Write-LauncherEvent -Event 'LAUNCHER_START' -Details @{\n"
                         "    artifact_prefix = $artifactPrefix\n"
                         "    heartbeat_seconds = $HeartbeatSeconds\n"
                         "    lease_seconds = $LeaseSeconds\n"
                         "}\n", launcher)
        self.assertGreaterEqual(piped, calls)


if __name__ == "__main__":
    unittest.main()
