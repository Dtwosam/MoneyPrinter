"""V2-9.7B.5 embedded launch-time Git provenance verification."""

import json
import shutil
import sqlite3
import subprocess
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.git_provenance import (
    GitProvenanceError,
    capture_git_provenance,
)
from printer_v1.operator_cli import operational_memory_factory_command
from printer_v1.operator_cli.one_command_15m_factory import (
    load_report_only,
    run_one_command_15m_factory,
)


EXPECTED_ZERO_TABLES = (
    "printer_source_requests",
    "printer_token_snapshots",
    "printer_memory_windows",
    "printer_episodes",
    "printer_memory_retrieval_queries",
    "printer_memory_retrieval_matches",
    "printer_paper_decisions",
    "printer_paper_positions",
    "printer_paper_trade_events",
    "printer_paper_trade_audits",
    "printer_paper_audit_reports",
)


class EmbeddedGitProvenanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _git(self, repo, *arguments):
        return subprocess.run(
            ["git", *arguments],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
            shell=False,
        )

    def _repo(self):
        repo = self.root / "repo with spaces"
        repo.mkdir()
        self._git(repo, "init")
        self._git(repo, "config", "user.email", "printer-tests@example.invalid")
        self._git(repo, "config", "user.name", "Printer Tests")
        (repo / "tracked.txt").write_text("clean\n", encoding="ascii")
        self._git(repo, "add", "tracked.txt")
        self._git(repo, "commit", "-m", "fixture")
        return repo

    def test_clean_repo_captures_exact_full_head(self):
        repo = self._repo()
        expected = self._git(repo, "rev-parse", "HEAD").stdout.strip()

        provenance = capture_git_provenance(
            repo, now=datetime(2026, 7, 17, tzinfo=timezone.utc)
        )

        self.assertEqual(expected, provenance["git_head"])
        self.assertTrue(provenance["git_tracked_tree_clean"])
        self.assertFalse(provenance["git_staged_changes_present"])
        self.assertFalse(provenance["git_unstaged_changes_present"])
        self.assertFalse(provenance["git_untracked_present"])

    def test_staged_or_unstaged_tracked_changes_fail_closed(self):
        repo = self._repo()
        (repo / "tracked.txt").write_text("unstaged\n", encoding="ascii")
        with self.assertRaisesRegex(GitProvenanceError, "tracked tree is dirty"):
            capture_git_provenance(repo)

        self._git(repo, "add", "tracked.txt")
        with self.assertRaisesRegex(GitProvenanceError, "tracked tree is dirty"):
            capture_git_provenance(repo)

    def test_untracked_only_is_recorded_without_dirtying_tracked_tree(self):
        repo = self._repo()
        (repo / "unrelated.txt").write_text("untracked\n", encoding="ascii")

        provenance = capture_git_provenance(repo)

        self.assertTrue(provenance["git_tracked_tree_clean"])
        self.assertTrue(provenance["git_untracked_present"])

    def test_exact_authoritative_sqlite_sidecars_may_be_allowed(self):
        repo = self._repo()
        allowed = (
            "data/printer_v1.sqlite3-journal",
            "data/printer_v1.sqlite3-wal",
            "data/printer_v1.sqlite3-shm",
        )
        (repo / "data").mkdir()
        for relative in allowed:
            (repo / relative).write_text("runtime companion", encoding="ascii")

        provenance = capture_git_provenance(
            repo, allowed_untracked_paths=allowed
        )

        self.assertFalse(provenance["git_untracked_present"])

    def test_sidecar_allowlist_still_reports_arbitrary_untracked_files(self):
        repo = self._repo()
        (repo / "data").mkdir()
        (repo / "data" / "printer_v1.sqlite3-journal").write_text(
            "runtime companion", encoding="ascii"
        )
        (repo / "unexpected.txt").write_text("blocked", encoding="ascii")

        provenance = capture_git_provenance(
            repo,
            allowed_untracked_paths=("data/printer_v1.sqlite3-journal",),
        )

        self.assertTrue(provenance["git_untracked_present"])

    def test_operational_provenance_permits_only_exact_runtime_sidecars(self):
        repo = self._repo()
        (repo / "data").mkdir()
        for name in (
            "printer_v1.sqlite3-journal",
            "printer_v1.sqlite3-wal",
            "printer_v1.sqlite3-shm",
        ):
            (repo / "data" / name).write_text(
                "runtime companion", encoding="ascii"
            )

        provenance = (
            operational_memory_factory_command._capture_operational_git_provenance(
                repo
            )
        )

        self.assertFalse(provenance["git_untracked_present"])

    def test_operational_provenance_blocks_arbitrary_untracked_files(self):
        repo = self._repo()
        (repo / "data").mkdir()
        (repo / "data" / "printer_v1.sqlite3-journal").write_text(
            "runtime companion", encoding="ascii"
        )
        (repo / "unexpected.txt").write_text("blocked", encoding="ascii")

        with self.assertRaisesRegex(
            GitProvenanceError, "arbitrary untracked file"
        ):
            operational_memory_factory_command._capture_operational_git_provenance(
                repo
            )

    def test_detached_head_is_supported(self):
        repo = self._repo()
        expected = self._git(repo, "rev-parse", "HEAD").stdout.strip()
        self._git(repo, "checkout", "--detach", expected)

        provenance = capture_git_provenance(repo)

        self.assertEqual(expected, provenance["git_head"])

    def test_git_environment_failures_fail_closed(self):
        repo = self._repo()
        with self.assertRaisesRegex(GitProvenanceError, "executable is unavailable"):
            capture_git_provenance(repo, git_executable="missing-git-executable")
        empty_repo = self.root / "empty-repo"
        empty_repo.mkdir()
        self._git(empty_repo, "init")
        with self.assertRaisesRegex(GitProvenanceError, "could not be verified"):
            capture_git_provenance(empty_repo)

        def timeout_runner(*_args, **_kwargs):
            raise subprocess.TimeoutExpired("git", 1)

        with self.assertRaisesRegex(GitProvenanceError, "timed out"):
            capture_git_provenance(repo, runner=timeout_runner)

        malformed = subprocess.CompletedProcess(
            args=["git"], returncode=0, stdout="not-a-sha\n", stderr=""
        )
        with self.assertRaisesRegex(GitProvenanceError, "HEAD output is malformed"):
            capture_git_provenance(repo, runner=lambda *_args, **_kwargs: malformed)

    def test_run_final_report_and_replay_preserve_one_launch_payload(self):
        repo = self._repo()
        provenance = capture_git_provenance(
            repo, now=datetime(2026, 7, 17, tzinfo=timezone.utc)
        )
        db = self.root / "proof.sqlite3"
        backup = self.root / "proof.backup.sqlite3"
        apply_migrations(db)
        shutil.copy2(db, backup)

        def empty_discovery(_args):
            return {
                "selection_handoff_report": {
                    "batch_id": None,
                    "selection_seed": "provenance-fixture",
                    "eligible_pool_size": 0,
                },
                "discovery_results": [],
            }

        with patch(
            "printer_v1.operator_cli.one_command_15m_factory.capture_git_provenance"
        ) as recapture:
            report = run_one_command_15m_factory(
                db,
                backup,
                operator_approved=True,
                proof_mode=True,
                discovery_runner=empty_discovery,
                launch_provenance=provenance,
            )
            recapture.assert_not_called()

        run_id = report["run_id"]
        conn = sqlite3.connect(db)
        try:
            config_text, final_text = conn.execute(
                """SELECT config_json, final_report_json
                   FROM printer_memory_factory_runs WHERE run_id = ?""",
                (run_id,),
            ).fetchone()
            before_replay = (config_text, final_text)
            counts = {
                table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in EXPECTED_ZERO_TABLES
            }
        finally:
            conn.close()

        stored_config = json.loads(config_text)
        stored_report = json.loads(final_text)
        with patch(
            "printer_v1.operator_cli.git_provenance.capture_git_provenance"
        ) as recapture:
            replay = load_report_only(db, run_id)
            recapture.assert_not_called()

        conn = sqlite3.connect(db)
        try:
            after_replay = conn.execute(
                """SELECT config_json, final_report_json
                   FROM printer_memory_factory_runs WHERE run_id = ?""",
                (run_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertEqual(provenance, stored_config["git_provenance"])
        self.assertEqual(provenance, stored_report["git_provenance"])
        self.assertEqual(provenance, replay["git_provenance"])
        self.assertEqual(before_replay, after_replay)
        self.assertEqual("REPORT_ONLY", replay["replay"]["mode"])
        self.assertEqual(0, replay["replay"]["new_source_calls"])
        self.assertEqual(0, replay["replay"]["new_evidence_rows"])
        self.assertEqual({table: 0 for table in EXPECTED_ZERO_TABLES}, counts)

    def test_launcher_propagates_same_payload_without_branch_or_diff_capture(self):
        script = (
            Path(__file__).resolve().parents[1] / "scripts" / "Start-V2-9-Proof.ps1"
        ).read_text(encoding="utf-8")

        self.assertIn("printer_v1.operator_cli.git_provenance", script)
        self.assertIn("'--git-provenance-json', $gitProvenanceJson", script)
        self.assertGreaterEqual(script.count("git_provenance = $gitProvenance"), 2)
        self.assertNotIn("git branch", script.lower())
        self.assertNotIn("git diff", script.lower())


if __name__ == "__main__":
    unittest.main()
