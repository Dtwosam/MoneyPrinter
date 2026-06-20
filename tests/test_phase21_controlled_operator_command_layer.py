import contextlib
import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import tomllib
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_cli import commands, formatting
from printer_v1.operator_db.bootstrap import initialize_operator_db
from printer_v1.operator_db.paths import get_default_db_path


class Phase21ControlledOperatorCommandLayerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp_root = pathlib.Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def run_command(self, fn, argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            exit_code = fn(argv)
        return exit_code, stream.getvalue()

    def parse_json_output(self, output):
        self.assertNotIn("{'command'", output)
        return json.loads(output)

    def table_count(self, db_path, table_name):
        connection = sqlite3.connect(db_path)
        try:
            return int(connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])
        finally:
            connection.close()

    def test_operator_cli_files_import_successfully(self):
        self.assertTrue((PROJECT_ROOT / "src" / "printer_v1" / "operator_cli" / "__init__.py").is_file())
        self.assertTrue((PROJECT_ROOT / "src" / "printer_v1" / "operator_cli" / "commands.py").is_file())
        self.assertTrue((PROJECT_ROOT / "src" / "printer_v1" / "operator_cli" / "formatting.py").is_file())
        self.assertIsNotNone(commands.main_db_status)
        self.assertIsNotNone(formatting.format_json_output)

    def test_pyproject_exposes_required_console_scripts(self):
        pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        scripts = pyproject["project"]["scripts"]
        expected = {
            "printer-init-db": "printer_v1.operator_cli.commands:main_init_db",
            "printer-db-status": "printer_v1.operator_cli.commands:main_db_status",
            "printer-db-counts": "printer_v1.operator_cli.commands:main_db_counts",
            "printer-migration-status": "printer_v1.operator_cli.commands:main_migration_status",
            "printer-operator-report": "printer_v1.operator_cli.commands:main_operator_report",
            "printer-synthetic-validation": "printer_v1.operator_cli.commands:main_synthetic_validation",
            "printer-readiness-check": "printer_v1.operator_cli.commands:main_readiness_check",
            "printer-source-smoke-dexscreener": "printer_v1.operator_cli.commands:main_source_smoke_dexscreener",
            "printer-manual-intake-token-pair": "printer_v1.operator_cli.commands:main_manual_intake_token_pair",
            "printer-collect-token-snapshots-once": "printer_v1.operator_cli.commands:main_collect_token_snapshots_once",
            "printer-collect-context-once": "printer_v1.operator_cli.commands:main_collect_context_once",
        }
        self.assertEqual({key: scripts[key] for key in expected}, expected)

    def test_formatting_helpers_produce_json_and_text(self):
        payload = {"state_classification": "NO_PERSISTENT_DB_FOUND", "exists": False, "db_path": "missing"}
        self.assertIn('"state_classification"', formatting.format_json_output(payload))
        self.assertIn("NO_PERSISTENT_DB_FOUND", formatting.format_text_output(payload))
        self.assertIn("printer_tokens", formatting.format_counts_table({"printer_tokens": 0}))

    def test_db_status_does_not_initialize_missing_db(self):
        db_path = self.temp_root / "missing.sqlite3"
        exit_code, output = self.run_command(
            commands.main_db_status,
            ["--project-root", str(self.temp_root), "--db-path", str(db_path), "--format", "json"],
        )
        payload = self.parse_json_output(output)
        self.assertEqual(exit_code, 0)
        self.assertFalse(db_path.exists())
        self.assertEqual(payload["state_classification"], "NO_PERSISTENT_DB_FOUND")
        self.assertIn("NO_PERSISTENT_DB_FOUND", output)

    def test_init_db_creates_schema_only_temp_db(self):
        exit_code, output = self.run_command(
            commands.main_init_db,
            ["--project-root", str(self.temp_root), "--format", "json"],
        )
        payload = self.parse_json_output(output)
        self.assertEqual(exit_code, 0)
        db_path = get_default_db_path(self.temp_root)
        self.assertTrue(db_path.is_file())
        self.assertEqual(payload["latest_migration"], "020_hardening_synthetic_validation.sql")
        self.assertEqual(payload["state_classification"], "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")
        for table in (
            "printer_tokens",
            "printer_token_snapshots",
            "printer_memory_windows",
            "printer_episodes",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_scheduler_jobs",
        ):
            self.assertEqual(self.table_count(db_path, table), 0, table)

    def test_counts_and_migration_status_commands_are_read_only(self):
        initialize_operator_db(project_root=self.temp_root)
        db_path = get_default_db_path(self.temp_root)
        before = self.table_count(db_path, "printer_operator_review_reports")
        counts_exit, counts_output = self.run_command(
            commands.main_db_counts,
            ["--project-root", str(self.temp_root), "--format", "json"],
        )
        migration_exit, migration_output = self.run_command(
            commands.main_migration_status,
            ["--project-root", str(self.temp_root), "--format", "json"],
        )
        counts_payload = self.parse_json_output(counts_output)
        migration_payload = self.parse_json_output(migration_output)
        self.assertEqual(counts_exit, 0)
        self.assertEqual(migration_exit, 0)
        self.assertEqual(counts_payload["counts"]["printer_tokens"], 0)
        self.assertEqual(migration_payload["latest_migration"], "020_hardening_synthetic_validation.sql")
        self.assertEqual(migration_payload["missing_migrations"], [])
        self.assertEqual(self.table_count(db_path, "printer_operator_review_reports"), before)

    def test_operator_report_preview_is_read_only_and_record_writes_review_rows_only(self):
        initialize_operator_db(project_root=self.temp_root)
        db_path = get_default_db_path(self.temp_root)
        preview_exit, preview_output = self.run_command(
            commands.main_operator_report,
            ["--project-root", str(self.temp_root), "--scope", "REPORT_DB_STATE", "--format", "json"],
        )
        preview_payload = self.parse_json_output(preview_output)
        self.assertEqual(preview_exit, 0)
        self.assertFalse(preview_payload["recorded"])
        self.assertEqual(self.table_count(db_path, "printer_operator_review_reports"), 0)
        self.assertEqual(self.table_count(db_path, "printer_operator_review_items"), 0)
        before_counts = {
            "printer_tokens": self.table_count(db_path, "printer_tokens"),
            "printer_memory_windows": self.table_count(db_path, "printer_memory_windows"),
            "printer_paper_decisions": self.table_count(db_path, "printer_paper_decisions"),
            "printer_paper_positions": self.table_count(db_path, "printer_paper_positions"),
            "printer_scheduler_jobs": self.table_count(db_path, "printer_scheduler_jobs"),
        }
        record_exit, record_output = self.run_command(
            commands.main_operator_report,
            ["--project-root", str(self.temp_root), "--scope", "REPORT_DB_STATE", "--record", "--format", "json"],
        )
        record_payload = self.parse_json_output(record_output)
        self.assertEqual(record_exit, 0)
        self.assertTrue(record_payload["recorded"])
        self.assertEqual(self.table_count(db_path, "printer_operator_review_reports"), 1)
        self.assertGreaterEqual(self.table_count(db_path, "printer_operator_review_items"), 1)
        for table_name, count in before_counts.items():
            self.assertEqual(self.table_count(db_path, table_name), count, table_name)

    def test_synthetic_validation_uses_temp_db_by_default(self):
        exit_code, output = self.run_command(
            commands.main_synthetic_validation,
            ["--project-root", str(self.temp_root), "--format", "json"],
        )
        payload = self.parse_json_output(output)
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["completed_stage"], "FLOW_STAGE_COMPLETE")
        self.assertTrue(payload["synthetic_only"])
        self.assertTrue(payload["temp_db_only"])
        self.assertFalse(payload["project_db_created"])
        self.assertFalse(payload["used_explicit_db_path"])
        self.assertFalse(get_default_db_path(self.temp_root).exists())
        self.assertIn("FLOW_STAGE_COMPLETE", output)

    def test_readiness_check_missing_and_schema_only_states(self):
        missing_exit, missing_output = self.run_command(
            commands.main_readiness_check,
            ["--project-root", str(self.temp_root), "--format", "json"],
        )
        missing_payload = self.parse_json_output(missing_output)
        self.assertEqual(missing_exit, 0)
        self.assertEqual(missing_payload["readiness_label"], "NEEDS_DB_INIT")
        self.assertFalse(get_default_db_path(self.temp_root).exists())
        initialize_operator_db(project_root=self.temp_root)
        ready_exit, ready_output = self.run_command(
            commands.main_readiness_check,
            ["--project-root", str(self.temp_root), "--format", "json"],
        )
        ready_payload = self.parse_json_output(ready_output)
        self.assertEqual(ready_exit, 0)
        self.assertEqual(ready_payload["readiness_label"], "READY_SCHEMA_ONLY")
        self.assertFalse(ready_payload["runtime_has_started"])

    def test_gitignore_protects_db_and_egg_info_files(self):
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            "*.db",
            "*.sqlite",
            "*.sqlite3",
            "*.db3",
            "data/*.sqlite3",
            "*.egg-info/",
            "src/*.egg-info/",
            "src/**/*.egg-info/",
        ):
            self.assertIn(pattern, gitignore)

    def test_commands_do_not_create_project_root_db_or_forbidden_capabilities(self):
        project_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        existed_before = project_db.exists()
        self.run_command(commands.main_db_status, ["--project-root", str(self.temp_root), "--format", "json"])
        self.run_command(commands.main_db_counts, ["--project-root", str(self.temp_root), "--format", "json"])
        self.run_command(commands.main_migration_status, ["--project-root", str(self.temp_root), "--format", "json"])
        self.assertEqual(project_db.exists(), existed_before)
        source_text = (PROJECT_ROOT / "src" / "printer_v1" / "operator_cli" / "commands.py").read_text(encoding="utf-8")
        forbidden_fragments = [
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "while True",
            "APScheduler",
            "FastAPI",
            "Flask",
            "Django",
            "React",
            "Vue",
            "Svelte",
            "private_key",
            "wallet_address",
            "signed_tx",
            "execute_trade",
            "live_trade",
            "transaction_signature",
            "tx_signature",
            "confidence_score",
            "buy_score",
            "ranking_score",
            "rank_score",
            "embedding",
            "vector",
        ]
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, source_text)

    def test_main_entrypoints_return_zero_and_print_once(self):
        initialize_operator_db(project_root=self.temp_root)
        db_path = get_default_db_path(self.temp_root)
        checks = [
            (commands.main_db_status, ["--db-path", str(db_path), "--format", "json"]),
            (commands.main_db_counts, ["--db-path", str(db_path), "--format", "json"]),
            (commands.main_migration_status, ["--db-path", str(db_path), "--format", "json"]),
            (commands.main_readiness_check, ["--db-path", str(db_path), "--project-root", str(self.temp_root), "--format", "json"]),
        ]
        for fn, argv in checks:
            exit_code, output = self.run_command(fn, argv)
            self.assertEqual(exit_code, 0, fn.__name__)
            self.assertIsInstance(exit_code, int)
            self.assertNotIsInstance(exit_code, dict)
            self.assertEqual(output.lstrip().find("{"), 0, fn.__name__)
            self.assertNotIn("{'command'", output)
            self.parse_json_output(output)


if __name__ == "__main__":
    unittest.main()
