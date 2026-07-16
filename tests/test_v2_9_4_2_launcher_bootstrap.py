"""V2-9.4.2 Windows PowerShell launcher bootstrap fixtures."""

from __future__ import annotations

import hashlib
from pathlib import Path
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "Start-V2-9-Proof.ps1"
RUNS = ROOT / "operator-runs"
PERSISTENT_DB = ROOT / "data" / "printer_v1.sqlite3"
LOCK = RUNS / "v2-9-one-proof.lock.json"
POWERSHELL = shutil.which("powershell.exe")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class LauncherBootstrapTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if POWERSHELL is None:
            raise unittest.SkipTest("Windows PowerShell 5.1 is required")
        cls.persistent_hash = _sha256(PERSISTENT_DB)
        cls.attempt6_before = {
            path.name for path in RUNS.glob("v2-9-attempt6-*")
        } if RUNS.exists() else set()
        cls.lock_before = LOCK.exists()

    def _invoke(self, *arguments: str) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            [
                str(POWERSHELL),
                "-NoProfile",
                "-NonInteractive",
                "-File",
                str(SCRIPT),
                "-AttemptNumber",
                "6",
                *arguments,
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(_sha256(PERSISTENT_DB), self.persistent_hash)
        current = {
            path.name for path in RUNS.glob("v2-9-attempt6-*")
        } if RUNS.exists() else set()
        self.assertEqual(current, self.attempt6_before)
        self.assertEqual(LOCK.exists(), self.lock_before)
        return result

    def test_windows_powershell_51_parser_accepts_launcher(self) -> None:
        escaped = str(SCRIPT).replace("'", "''")
        command = (
            "$tokens=$null;$errors=$null;"
            f"[Management.Automation.Language.Parser]::ParseFile('{escaped}',"
            "[ref]$tokens,[ref]$errors)|Out-Null;"
            "if(@($errors).Count -ne 0){$errors|ForEach-Object{$_.Message};exit 1};"
            "$PSVersionTable.PSVersion.ToString()"
        )
        result = subprocess.run(
            [str(POWERSHELL), "-NoProfile", "-NonInteractive", "-Command", command],
            cwd=ROOT,
            text=True,
            capture_output=True,
            timeout=20,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(result.stdout.strip().startswith("5.1."))

    def test_file_invocation_without_project_root_reaches_approval_boundary(self) -> None:
        result = self._invoke()
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("V2-9 proof launch requires -OperatorApproved.", combined)
        self.assertNotIn("Split-Path", combined)
        self.assertNotIn("Cannot bind argument to parameter 'Path'", combined)

    def test_explicit_valid_project_root_reaches_approval_boundary(self) -> None:
        result = self._invoke("-ProjectRoot", str(ROOT))
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("V2-9 proof launch requires -OperatorApproved.", combined)
        self.assertNotIn("Split-Path", combined)

    def test_invalid_project_root_fails_clearly_before_any_artifact(self) -> None:
        invalid = ROOT / "__missing_v2_9_4_2_root__"
        self.assertFalse(invalid.exists())
        result = self._invoke("-ProjectRoot", str(invalid))
        combined = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("V2-9 project root is unavailable:", combined)
        self.assertNotIn("V2-9 proof launch requires -OperatorApproved.", combined)

    def test_param_block_does_not_evaluate_psscriptroot(self) -> None:
        launcher = SCRIPT.read_text(encoding="utf-8")
        param_block = launcher.split(")\n\n", 1)[0]
        self.assertIn("[string]$ProjectRoot,", param_block)
        self.assertNotIn("$PSScriptRoot", param_block)
        self.assertIn(
            "if ([string]::IsNullOrWhiteSpace($PSScriptRoot))",
            launcher,
        )
        self.assertIn(
            "V2-9 launcher script root is unavailable; specify -ProjectRoot.",
            launcher,
        )
        self.assertIn("-LiteralPath $ProjectRoot -ErrorAction Stop", launcher)


if __name__ == "__main__":
    unittest.main()
