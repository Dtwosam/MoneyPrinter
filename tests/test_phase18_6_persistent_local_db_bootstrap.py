import inspect
import pathlib
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.operator_db import bootstrap, paths, status
from printer_v1.operator_db.bootstrap import (
    get_operator_db_bootstrap_report,
    initialize_operator_db,
    operator_db_exists,
)
from printer_v1.operator_db.paths import (
    db_path_is_inside_project_data_dir,
    db_path_is_sqlite_file,
    ensure_data_dir_exists,
    get_default_data_dir,
    get_default_db_path,
    resolve_operator_db_path,
)
from printer_v1.operator_db.status import (
    classify_operator_db_state,
    get_core_table_counts,
    get_operator_db_status,
    get_schema_migration_status,
    memory_has_started,
    paper_trading_has_started,
    runtime_has_started,
)


class Phase18Point6PersistentLocalDbBootstrapTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp_root = pathlib.Path(self.tempdir.name)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_operator_db_files_import(self):
        for module in (bootstrap, paths, status):
            self.assertTrue(inspect.ismodule(module))

    def test_default_path_and_explicit_resolution(self):
        default_data_dir = get_default_data_dir(self.temp_root)
        default_db_path = get_default_db_path(self.temp_root)
        self.assertEqual(default_data_dir, self.temp_root / "data")
        self.assertEqual(default_db_path, self.temp_root / "data" / "printer_v1.sqlite3")
        self.assertFalse(default_data_dir.exists())
        self.assertFalse(default_db_path.exists())
        self.assertEqual(resolve_operator_db_path(project_root=self.temp_root), default_db_path.resolve(strict=False))
        explicit = self.temp_root / "custom.sqlite3"
        self.assertEqual(resolve_operator_db_path(explicit, self.temp_root), explicit.resolve(strict=False))
        self.assertTrue(db_path_is_sqlite_file(explicit))
        self.assertTrue(db_path_is_inside_project_data_dir(default_db_path, self.temp_root))
        self.assertFalse(db_path_is_inside_project_data_dir(explicit, self.temp_root))

    def test_data_directory_is_created_only_when_requested(self):
        data_dir = get_default_data_dir(self.temp_root)
        db_path = get_default_db_path(self.temp_root)
        resolve_operator_db_path(project_root=self.temp_root)
        self.assertFalse(data_dir.exists())
        self.assertFalse(db_path.exists())
        created = ensure_data_dir_exists(data_dir)
        self.assertEqual(created, data_dir.resolve(strict=False))
        self.assertTrue(data_dir.is_dir())
        self.assertFalse(db_path.exists())

    def test_initialize_operator_db_creates_schema_only(self):
        report = initialize_operator_db(project_root=self.temp_root)
        db_path = get_default_db_path(self.temp_root)
        self.assertTrue(db_path.is_file())
        self.assertTrue(operator_db_exists(project_root=self.temp_root))
        self.assertEqual(report["db_path"], str(db_path.resolve(strict=False)))
        schema = get_schema_migration_status(db_path)
        self.assertEqual(schema["latest_migration"], "020_hardening_synthetic_validation.sql")
        self.assertEqual(len(schema["applied_migrations"]), 20)
        counts = get_core_table_counts(db_path)
        self.assertEqual(counts["printer_schema_migrations"], 20)
        for table in (
            "printer_tokens",
            "printer_token_snapshots",
            "printer_market_regime_snapshots",
            "printer_solana_chain_heat_snapshots",
            "printer_safety_rug_snapshots",
            "printer_liquidity_exit_snapshots",
            "printer_trading_flow_snapshots",
            "printer_chart_volatility_snapshots",
            "printer_micro_events",
            "printer_memory_windows",
            "printer_episodes",
            "printer_episode_snapshots",
            "printer_episode_outcomes",
            "printer_memory_fingerprints",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_scheduler_jobs",
        ):
            self.assertEqual(counts[table], 0, table)
        self.assertEqual(classify_operator_db_state(db_path), "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")

    def test_missing_db_status_and_schema_only_flags(self):
        missing = self.temp_root / "missing.sqlite3"
        self.assertEqual(classify_operator_db_state(missing), "NO_PERSISTENT_DB_FOUND")
        self.assertFalse(memory_has_started(missing))
        self.assertFalse(paper_trading_has_started(missing))
        self.assertFalse(runtime_has_started(missing))
        self.assertEqual(get_core_table_counts(missing)["printer_tokens"], None)
        initialize_operator_db(project_root=self.temp_root)
        db_path = get_default_db_path(self.temp_root)
        db_status = get_operator_db_status(db_path)
        self.assertEqual(db_status["state_classification"], "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")
        self.assertFalse(db_status["memory_has_started"])
        self.assertFalse(db_status["paper_trading_has_started"])
        self.assertFalse(db_status["runtime_has_started"])

    def test_explicit_temp_db_path_and_bootstrap_report(self):
        explicit = self.temp_root / "nested" / "operator.db3"
        report = initialize_operator_db(explicit, project_root=self.temp_root)
        self.assertTrue(explicit.is_file())
        self.assertEqual(report["status"]["state_classification"], "PERSISTENT_DB_EMPTY_SCHEMA_ONLY")
        second = get_operator_db_bootstrap_report(explicit, project_root=self.temp_root)
        self.assertEqual(second["schema"]["latest_migration"], "020_hardening_synthetic_validation.sql")
        self.assertEqual(second["status"]["table_counts"]["printer_tokens"], 0)

    def test_status_helpers_are_read_only(self):
        initialize_operator_db(project_root=self.temp_root)
        db_path = get_default_db_path(self.temp_root)
        before = get_core_table_counts(db_path)
        for _ in range(3):
            get_operator_db_status(db_path)
            get_schema_migration_status(db_path)
            classify_operator_db_state(db_path)
            memory_has_started(db_path)
            paper_trading_has_started(db_path)
            runtime_has_started(db_path)
        after = get_core_table_counts(db_path)
        self.assertEqual(before, after)

    def test_no_project_root_persistent_db_created_by_tests(self):
        project_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        existed_before = project_db.exists()
        self.assertEqual(project_db.exists(), existed_before)
        self.assertFalse((self.temp_root / "data" / "printer_v1.sqlite3").exists())

    def test_gitignore_protects_local_db_patterns(self):
        gitignore = (PROJECT_ROOT / ".gitignore").read_text(encoding="utf-8")
        for pattern in (
            "data/*.sqlite",
            "data/*.sqlite3",
            "data/*.db",
            "data/*.db3",
            "*.sqlite",
            "*.sqlite3",
            "*.db",
            "*.db3",
        ):
            self.assertIn(pattern, gitignore)

    def test_no_runtime_network_scheduler_or_forbidden_capabilities(self):
        source_text = "\n".join(inspect.getsource(module) for module in (bootstrap, paths, status))
        for fragment in (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "claim_due_job",
            "complete_job",
            "while True",
            "APScheduler",
            "FastAPI",
            "Flask",
            "Django",
            "React",
            "Vue",
            "Svelte",
            "confidence_score",
            "buy_score",
            "ranking_score",
            "rank_score",
            "score =",
            "confidence =",
            "embedding",
            "vector",
        ):
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()
