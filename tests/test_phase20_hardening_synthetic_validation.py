import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.hardening import contracts, fixtures, flow_validation, recorder, reports, schema_checks


class Phase20HardeningSyntheticValidationTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.temp_root = pathlib.Path(self.tempdir.name)
        self.db_path = self.temp_root / "phase20.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()
        self.tempdir.cleanup()

    def table_names(self):
        return {
            row["name"]
            for row in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }

    def column_names(self, table_name):
        return {
            row["name"]
            for row in self.connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }

    def table_count(self, table_name):
        return int(self.connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0])

    def test_operator_review_package_exists_and_hardening_imports(self):
        self.assertTrue((PROJECT_ROOT / "src" / "printer_v1" / "operator_review" / "__init__.py").is_file())
        self.assertTrue((PROJECT_ROOT / "src" / "printer_v1" / "hardening" / "__init__.py").is_file())
        self.assertIsNotNone(contracts.ValidationScopeLabel.VALIDATION_SCHEMA)
        self.assertIsNotNone(fixtures.build_synthetic_solana_token_fixture)
        self.assertIsNotNone(schema_checks.check_required_tables_exist)
        self.assertIsNotNone(flow_validation.run_full_synthetic_validation_flow)
        self.assertIsNotNone(reports.build_validation_run_report)
        self.assertIsNotNone(recorder.record_validation_run)

    def test_required_phase20_labels_exist(self):
        self.assertEqual(
            contracts.VALIDATION_SCOPE_LABELS,
            {
                "VALIDATION_SCHEMA",
                "VALIDATION_CONTRACTS",
                "VALIDATION_MIGRATIONS",
                "VALIDATION_SYNTHETIC_DISCOVERY",
                "VALIDATION_SYNTHETIC_SNAPSHOTS",
                "VALIDATION_SYNTHETIC_CONTEXT",
                "VALIDATION_SYNTHETIC_MEMORY",
                "VALIDATION_SYNTHETIC_RETRIEVAL",
                "VALIDATION_SYNTHETIC_PAPER_DECISION",
                "VALIDATION_SYNTHETIC_PAPER_MONITOR",
                "VALIDATION_SYNTHETIC_PAPER_AUDIT",
                "VALIDATION_SYNTHETIC_OPERATOR_REPORT",
                "VALIDATION_FULL_SYNTHETIC_FLOW",
                "VALIDATION_UNKNOWN_SCOPE",
            },
        )
        self.assertEqual(
            contracts.VALIDATION_RESULT_LABELS,
            {
                "VALIDATION_PASS",
                "VALIDATION_PASS_WITH_WARNINGS",
                "VALIDATION_FAIL",
                "VALIDATION_SKIPPED",
                "VALIDATION_INCOMPLETE",
                "VALIDATION_UNKNOWN",
            },
        )
        self.assertIn("VALIDATION_ISSUE_DECISION_WITHOUT_CLEAN_MEMORY", contracts.VALIDATION_ISSUE_LABELS)
        self.assertIn("VALIDATION_ISSUE_POSITION_WITHOUT_VALID_DECISION", contracts.VALIDATION_ISSUE_LABELS)
        self.assertIn("FLOW_STAGE_COMPLETE", contracts.SYNTHETIC_FLOW_STAGE_LABELS)

    def test_migration_creates_validation_tables_without_forbidden_columns(self):
        self.assertIn("printer_validation_runs", self.table_names())
        self.assertIn("printer_validation_items", self.table_names())
        forbidden = {
            "score",
            "confidence",
            "rank",
            "rating",
            "weight",
            "wallet_address",
            "private_key",
            "signed_tx",
            "live_trade",
            "transaction_signature",
            "tx_signature",
            "execute_trade",
        }
        self.assertFalse(self.column_names("printer_validation_runs") & forbidden)
        self.assertFalse(self.column_names("printer_validation_items") & forbidden)

    def test_fixture_builders_are_deterministic_fake_and_local(self):
        first = fixtures.build_synthetic_solana_token_fixture()
        second = fixtures.build_synthetic_solana_token_fixture()
        self.assertEqual(first, second)
        self.assertEqual(first["chain"], "solana")
        self.assertIn("synthetic", first["token_mint"])
        all_payloads = [
            first,
            fixtures.build_synthetic_pair_fixture(),
            fixtures.build_synthetic_discovery_payload(),
            fixtures.build_synthetic_safety_context(),
            fixtures.build_synthetic_liquidity_exit_context(),
            fixtures.build_synthetic_trading_flow_context(),
            fixtures.build_synthetic_chart_volatility_context(),
            fixtures.build_synthetic_micro_event_context(),
            fixtures.build_synthetic_market_regime_context(),
            fixtures.build_synthetic_chain_heat_context(),
            fixtures.build_synthetic_clean_memory_episode_payload(),
            fixtures.build_synthetic_paper_decision_payload(),
        ]
        forbidden_keys = {"private_key", "wallet_address", "signed_tx", "tx_signature", "transaction_signature"}
        for payload in all_payloads:
            self.assertFalse(set(payload) & forbidden_keys)
            self.assertNotIn("score", payload)
            self.assertNotIn("confidence", payload)
            self.assertNotIn("rank", payload)

    def test_schema_checks_confirm_required_tables_and_detect_bad_temp_column(self):
        required = schema_checks.check_required_tables_exist(self.connection)
        self.assertEqual(required["validation_result_label"], "VALIDATION_PASS")
        validation_tables = schema_checks.check_validation_tables_exist(self.connection)
        self.assertEqual(validation_tables["validation_result_label"], "VALIDATION_PASS")
        self.assertEqual(schema_checks.check_forbidden_columns_absent(self.connection)["validation_result_label"], "VALIDATION_PASS")
        self.connection.execute("CREATE TABLE intentionally_bad_temp_table (id INTEGER PRIMARY KEY, score TEXT)")
        bad = schema_checks.check_forbidden_columns_absent(self.connection)
        self.assertEqual(bad["validation_result_label"], "VALIDATION_FAIL")
        self.assertEqual(bad["validation_issue_label"], "VALIDATION_ISSUE_FORBIDDEN_COLUMN")

    def test_contract_and_source_hardening_checks_are_read_only(self):
        before_files = sorted(path.relative_to(PROJECT_ROOT) for path in (PROJECT_ROOT / "src" / "printer_v1").rglob("*.py"))
        self.assertEqual(schema_checks.check_contract_label_consistency()["validation_result_label"], "VALIDATION_PASS")
        self.assertEqual(schema_checks.check_no_live_capability_terms_in_source(PROJECT_ROOT)["validation_result_label"], "VALIDATION_PASS")
        self.assertEqual(schema_checks.check_no_runtime_loop_terms_in_source(PROJECT_ROOT)["validation_result_label"], "VALIDATION_PASS")
        after_files = sorted(path.relative_to(PROJECT_ROOT) for path in (PROJECT_ROOT / "src" / "printer_v1").rglob("*.py"))
        self.assertEqual(before_files, after_files)

    def test_source_hardening_ignores_lock_vocabulary_but_blocks_capabilities(self):
        package = self.temp_root / "src" / "printer_v1"
        package.mkdir(parents=True)
        source = package / "audit_report.py"
        source.write_text(
            'LOCKS = {"private_key": False, "embedding": False, "vector": False}\n',
            encoding="utf-8",
        )
        self.assertEqual(
            schema_checks.check_no_live_capability_terms_in_source(self.temp_root)["validation_result_label"],
            "VALIDATION_PASS",
        )
        source.write_text("private_key = load_secret()\n", encoding="utf-8")
        blocked = schema_checks.check_no_live_capability_terms_in_source(self.temp_root)
        self.assertEqual(blocked["validation_result_label"], "VALIDATION_FAIL")
        self.assertEqual(blocked["item_payload"]["findings"][0]["term"], "private_key")

    def test_source_hardening_allows_adapter_transport_but_blocks_direct_bypass(self):
        package = self.temp_root / "src" / "printer_v1"
        sources = package / "sources"
        sources.mkdir(parents=True)
        (sources / "approved.py").write_text(
            "from urllib import request as url_request\n", encoding="utf-8"
        )
        self.assertEqual(
            schema_checks.check_no_live_capability_terms_in_source(self.temp_root)["validation_result_label"],
            "VALIDATION_PASS",
        )
        (package / "bypass.py").write_text("import httpx\n", encoding="utf-8")
        blocked = schema_checks.check_no_live_capability_terms_in_source(self.temp_root)
        self.assertEqual(blocked["validation_result_label"], "VALIDATION_FAIL")
        self.assertIn("direct_network_import:httpx", blocked["item_payload"]["findings"][0]["term"])
        (package / "bypass.py").write_text(
            "from urllib import request as url_request\n", encoding="utf-8"
        )
        blocked = schema_checks.check_no_live_capability_terms_in_source(self.temp_root)
        self.assertEqual(blocked["validation_result_label"], "VALIDATION_FAIL")
        self.assertIn("direct_network_import:urllib", blocked["item_payload"]["findings"][0]["term"])

    def test_runtime_hardening_distinguishes_bounded_and_unbounded_loops(self):
        package = self.temp_root / "src" / "printer_v1"
        package.mkdir(parents=True)
        source = package / "runner.py"
        source.write_text(
            "def run(max_duration_seconds, elapsed):\n"
            "    while True:\n"
            "        if elapsed() >= max_duration_seconds:\n"
            "            break\n",
            encoding="utf-8",
        )
        self.assertEqual(
            schema_checks.check_no_runtime_loop_terms_in_source(self.temp_root)["validation_result_label"],
            "VALIDATION_PASS",
        )
        source.write_text("while True:\n    run_once()\n", encoding="utf-8")
        blocked = schema_checks.check_no_runtime_loop_terms_in_source(self.temp_root)
        self.assertEqual(blocked["validation_result_label"], "VALIDATION_FAIL")
        self.assertEqual(blocked["item_payload"]["findings"][0]["term"], "unbounded_while_true")

    def test_synthetic_flow_seeds_discovery_snapshots_and_context(self):
        seeded = flow_validation.seed_synthetic_discovery_and_snapshots(self.connection)
        self.assertEqual(seeded["stage"], "FLOW_STAGE_SNAPSHOTS")
        self.assertGreater(self.table_count("printer_tokens"), 0)
        self.assertGreater(self.table_count("printer_pairs"), 0)
        self.assertGreater(self.table_count("printer_discovery_candidates"), 0)
        self.assertEqual(self.table_count("printer_token_snapshots"), 4)
        context = flow_validation.seed_synthetic_context_engine_rows(self.connection)
        self.assertEqual(context["stage"], "FLOW_STAGE_CONTEXT")
        for table in (
            "printer_safety_rug_snapshots",
            "printer_liquidity_exit_snapshots",
            "printer_trading_flow_snapshots",
            "printer_chart_volatility_snapshots",
            "printer_micro_events",
        ):
            self.assertGreater(self.table_count(table), 0, table)

    def test_synthetic_memory_retrieval_decision_monitor_audit_and_review_flow(self):
        flow_validation.seed_synthetic_discovery_and_snapshots(self.connection)
        flow_validation.seed_synthetic_context_engine_rows(self.connection)
        memory = flow_validation.run_synthetic_memory_build(self.connection)
        self.assertGreater(memory["episode_id"], 0)
        self.assertGreater(self.table_count("printer_memory_windows"), 0)
        self.assertGreater(self.table_count("printer_episodes"), 0)
        self.assertGreater(self.table_count("printer_memory_fingerprints"), 0)
        retrieval = flow_validation.run_synthetic_memory_retrieval(self.connection)
        self.assertGreater(retrieval["retrieval_query_id"], 0)
        self.assertGreater(self.table_count("printer_memory_retrieval_matches"), 0)
        decision = flow_validation.run_synthetic_paper_decision(self.connection)
        self.assertGreater(decision["paper_decision_id"], 0)
        monitor = flow_validation.run_synthetic_paper_monitor(self.connection)
        self.assertGreater(monitor["paper_position_id"], 0)
        self.assertGreater(self.table_count("printer_paper_trade_events"), 0)
        audit = flow_validation.run_synthetic_paper_audit(self.connection)
        self.assertGreater(audit["paper_audit_report_id"], 0)
        review = flow_validation.run_synthetic_operator_review(self.connection)
        self.assertGreater(review["operator_review_report_id"], 0)

    def test_synthetic_gates_block_decision_without_clean_memory_and_position_without_decision(self):
        flow_validation.seed_synthetic_discovery_and_snapshots(self.connection)
        blocked_decision = flow_validation.run_synthetic_paper_decision(self.connection)
        self.assertEqual(blocked_decision["items"][0]["validation_issue_label"], "VALIDATION_ISSUE_DECISION_WITHOUT_CLEAN_MEMORY")
        self.assertEqual(self.table_count("printer_paper_decisions"), 0)
        blocked_position = flow_validation.run_synthetic_paper_monitor(self.connection)
        self.assertEqual(blocked_position["items"][0]["validation_issue_label"], "VALIDATION_ISSUE_POSITION_WITHOUT_VALID_DECISION")
        self.assertEqual(self.table_count("printer_paper_positions"), 0)

    def test_full_synthetic_validation_flow_records_run_and_items(self):
        flow_db = flow_validation.initialize_temp_validation_db(self.temp_root)
        self.assertTrue(str(flow_db).startswith(str(self.temp_root)))
        payload = flow_validation.run_full_synthetic_validation_flow(flow_db, project_root=PROJECT_ROOT)
        self.assertEqual(payload["completed_stage"], "FLOW_STAGE_COMPLETE")
        self.assertTrue(payload["synthetic_only"])
        self.assertTrue(payload["temp_db_only"])
        self.assertFalse(payload["project_db_created"])
        latest = recorder.get_latest_validation_run(flow_db, "VALIDATION_FULL_SYNTHETIC_FLOW")
        self.assertIsNotNone(latest)
        self.assertEqual(latest["validation_result_label"], "VALIDATION_PASS")
        items = recorder.get_validation_items(flow_db, latest["id"])
        self.assertTrue(any(item["flow_stage_label"] == "FLOW_STAGE_COMPLETE" for item in items))
        report = reports.build_validation_run_report(payload)
        self.assertTrue(reports.validation_report_passes(report))
        self.assertTrue(reports.report_is_synthetic_only(report))

    def test_no_project_root_db_or_runtime_capabilities_are_created(self):
        project_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        existed_before = project_db.exists()
        self.assertEqual(project_db.exists(), existed_before)
        self.assertEqual(self.table_count("printer_scheduler_jobs"), 0)
        self.assertEqual(self.table_count("printer_paper_decisions"), 0)
        self.assertEqual(self.table_count("printer_paper_positions"), 0)
        self.assertEqual(schema_checks.check_no_live_capability_terms_in_source(PROJECT_ROOT)["validation_result_label"], "VALIDATION_PASS")
        self.assertEqual(schema_checks.check_no_runtime_loop_terms_in_source(PROJECT_ROOT)["validation_result_label"], "VALIDATION_PASS")


if __name__ == "__main__":
    unittest.main()
