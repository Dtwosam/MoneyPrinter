import inspect
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.memory.contracts import ActionLessonLabel, EpisodeOutcomeLabel, MemoryQualityLabel
from printer_v1.memory.fingerprints import record_memory_fingerprint
from printer_v1.memory_retrieval import fingerprint_builder, matcher, query, recorder, reports, retriever
from printer_v1.memory_retrieval.contracts import (
    MatchReasonLabel,
    MatchStrengthLabel,
    MemoryEvidenceLabel,
    RetrievalQueryTypeLabel,
    RetrievalResultLabel,
)
from printer_v1.memory_retrieval.fingerprint_builder import build_current_setup_fingerprint
from printer_v1.memory_retrieval.matcher import (
    classify_match_strength,
    compare_fingerprints,
    memory_match_can_be_clean_evidence,
)
from printer_v1.memory_retrieval.recorder import build_and_record_memory_retrieval_report, enqueue_memory_retrieval_job
from printer_v1.memory_retrieval.reports import build_memory_comparison_report
from printer_v1.memory_retrieval.retriever import (
    build_retrieval_result_label,
    group_matches_by_outcome,
    retrieve_memory_matches_for_current_setup,
)
from printer_v1.scheduler.contracts import JobStatus


FORBIDDEN_COLUMNS = {"score", "confidence", "rank", "rating", "weight", "wallet_address", "private_key", "signed_tx", "live_trade", "vector", "embedding"}
FORBIDDEN_FRAGMENTS = {"score", "confidence", "rank", "rating", "weight", "private_key", "signed_tx", "live_trade", "vector", "embedding"}


class Phase15MemoryRetrievalTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
        self.token_id, self.pair_id = self.insert_token_pair("retrieval-mint", "retrieval-pair")
        self.other_token_id, self.other_pair_id = self.insert_token_pair("memory-mint-2", "memory-pair-2")

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def insert_token_pair(self, mint, pair):
        with self.connect() as connection:
            token_id = connection.execute("INSERT INTO printer_tokens (token_mint, chain) VALUES (?, 'solana')", (mint,)).lastrowid
            pair_id = connection.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source) VALUES (?, ?, 'raydium', 'local')",
                (token_id, pair),
            ).lastrowid
        return int(token_id), int(pair_id)

    def base_fingerprint(self, **overrides):
        payload = {
            "window_kind": "WINDOW_15M",
            "outcome_label": "SUSTAINED_PUMP",
            "market_regime_label": "RISK_ON",
            "chain_heat_label": "SOLANA_HOT",
            "safety_status_label": "SAFETY_CLEAN",
            "liquidity_state_label": "LIQUIDITY_USABLE",
            "exit_realism_label": "EXIT_REALISTIC",
            "flow_direction_label": "FLOW_ACCUMULATION",
            "flow_pressure_label": "PRESSURE_STRONG_INFLOW",
            "trend_structure_label": "TREND_UP",
            "volatility_label": "VOLATILITY_ELEVATED",
            "candle_path_label": "PATH_STEADY_CLIMB",
            "micro_event_state_label": "TRADABLE_MICRO_PUMP",
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }
        payload.update(overrides)
        return payload

    def insert_episode(self, *, quality="CLEAN_MEMORY", fingerprint=None, outcome="SUSTAINED_PUMP"):
        with self.connect() as connection:
            window_id = connection.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, closed_at, memory_status,
                    data_quality_label, memory_quality_label
                )
                VALUES (?, ?, 'WINDOW_15M', ?, ?, 'CLEAN_MEMORY', 'CLEAN_DATA', ?)
                """,
                (self.other_token_id, self.other_pair_id, (self.now - timedelta(minutes=15)).isoformat(), self.now.isoformat(), quality),
            ).lastrowid
            episode_id = connection.execute(
                """
                INSERT INTO printer_episodes (
                    memory_window_id, token_id, pair_id, episode_kind, episode_status,
                    memory_status, data_quality_label, window_kind, episode_outcome_label,
                    memory_quality_label, action_lesson_label
                )
                VALUES (?, ?, ?, 'TOKEN_WINDOW_EPISODE', 'EPISODE_BUILT', 'CLEAN_MEMORY',
                    'CLEAN_DATA', 'WINDOW_15M', ?, ?, 'ACTION_WAIT_FAILED')
                """,
                (window_id, self.other_token_id, self.other_pair_id, outcome, quality),
            ).lastrowid
        record_memory_fingerprint(self.db_path, int(episode_id), fingerprint or self.base_fingerprint(outcome_label=outcome), quality)
        return int(episode_id)

    def column_names(self, table):
        with self.connect() as connection:
            return {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_memory_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "memory" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "memory" / "init.py").exists())

    def test_memory_retrieval_files_import_successfully(self):
        for module in (fingerprint_builder, matcher, query, recorder, reports, retriever):
            self.assertTrue(inspect.ismodule(module))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in RetrievalQueryTypeLabel}, {"CURRENT_SETUP_QUERY", "TOKEN_PAIR_HISTORY_QUERY", "OUTCOME_LOOKBACK_QUERY", "CLEAN_MEMORY_ONLY_QUERY", "AUDIT_MEMORY_REVIEW_QUERY"})
        self.assertIn("EXACT_CONDITION_MATCH", {label.value for label in MatchStrengthLabel})
        self.assertIn("MATCH_LIQUIDITY_EXIT_CONTEXT", {label.value for label in MatchReasonLabel})
        self.assertIn("RETRIEVAL_HAS_CLEAN_MATCHES", {label.value for label in RetrievalResultLabel})
        self.assertIn("MEMORY_EVIDENCE_STRONG", {label.value for label in MemoryEvidenceLabel})

    def test_migration_tables_and_forbidden_columns(self):
        self.assertIn("retrieval_result_label", self.column_names("printer_memory_retrieval_queries"))
        self.assertIn("match_strength_label", self.column_names("printer_memory_retrieval_matches"))
        for table in ("printer_memory_retrieval_queries", "printer_memory_retrieval_matches"):
            self.assertEqual(self.column_names(table) & FORBIDDEN_COLUMNS, set(), table)

    def test_current_setup_fingerprint_is_label_only(self):
        fp = build_current_setup_fingerprint({"context": self.base_fingerprint()})
        encoded = json.dumps(fp)
        self.assertEqual(fp["flow_direction_label"], "FLOW_ACCUMULATION")
        for fragment in ("score", "confidence", "rank", "vector", "embedding"):
            self.assertNotIn(fragment, encoded)

    def test_matcher_strengths_and_clean_evidence_rules(self):
        current = self.base_fingerprint()
        self.assertEqual(classify_match_strength(current, self.base_fingerprint()), MatchStrengthLabel.EXACT_CONDITION_MATCH)
        strong = self.base_fingerprint(market_regime_label="FEAR")
        self.assertEqual(classify_match_strength(current, strong), MatchStrengthLabel.STRONG_CONDITION_MATCH)
        partial = self.base_fingerprint(safety_status_label="SAFETY_CAUTION", liquidity_state_label="LIQUIDITY_THIN", flow_direction_label="FLOW_CHOPPY", trend_structure_label="TREND_CHOPPY")
        self.assertEqual(classify_match_strength(current, partial), MatchStrengthLabel.PARTIAL_CONDITION_MATCH)
        weak = {"window_kind": "WINDOW_15M"}
        self.assertEqual(classify_match_strength(current, weak), MatchStrengthLabel.WEAK_CONDITION_MATCH)
        self.assertEqual(classify_match_strength({}, {}), MatchStrengthLabel.NO_USABLE_MATCH)
        payload = {"memory_quality_label": MemoryQualityLabel.CLEAN_MEMORY.value, **compare_fingerprints(current, strong)}
        self.assertTrue(memory_match_can_be_clean_evidence(payload))
        payload["memory_quality_label"] = MemoryQualityLabel.AUDIT_ONLY_MEMORY.value
        self.assertFalse(memory_match_can_be_clean_evidence(payload))

    def test_retrieval_filters_dirty_do_not_train_and_groups_outcomes(self):
        clean_id = self.insert_episode(quality="CLEAN_MEMORY")
        self.insert_episode(quality="DIRTY_MEMORY")
        self.insert_episode(quality="DO_NOT_TRAIN_MEMORY")
        matches = retrieve_memory_matches_for_current_setup(self.db_path, {"context": self.base_fingerprint(), "token_id": self.token_id})
        clean = [match for match in matches if match["included_as_clean_evidence"]]
        excluded = {match["match_strength_label"] for match in matches if not match["included_as_clean_evidence"]}
        self.assertEqual(clean[0]["episode_id"], clean_id)
        self.assertIn(MatchStrengthLabel.DIRTY_MEMORY_EXCLUDED.value, excluded)
        self.assertIn(MatchStrengthLabel.DO_NOT_TRAIN_EXCLUDED.value, excluded)
        self.assertEqual(group_matches_by_outcome(clean), {"SUSTAINED_PUMP": 1})
        self.assertEqual(build_retrieval_result_label(clean), RetrievalResultLabel.RETRIEVAL_HAS_CLEAN_MATCHES)
        self.assertEqual(build_retrieval_result_label([]), RetrievalResultLabel.RETRIEVAL_NO_MATCHES)
        self.assertEqual(
            build_retrieval_result_label([match for match in matches if match["match_strength_label"] in {MatchStrengthLabel.DIRTY_MEMORY_EXCLUDED.value, MatchStrengthLabel.DO_NOT_TRAIN_EXCLUDED.value}]),
            RetrievalResultLabel.RETRIEVAL_BLOCKED_NO_CLEAN_MEMORY,
        )

    def test_report_summarizes_without_action_recommendations(self):
        self.insert_episode()
        matches = retrieve_memory_matches_for_current_setup(self.db_path, {"context": self.base_fingerprint(), "token_id": self.token_id})
        report = build_memory_comparison_report({"query_type": "CURRENT_SETUP_QUERY"}, matches)
        self.assertIn("historical_outcomes", report)
        self.assertIsNone(report["recommendation"])
        encoded = json.dumps(report)
        for forbidden in ("BUY", "SELL", "HOLD"):
            self.assertNotIn(f'"{forbidden}"', encoded)

    def test_recorder_inserts_query_matches_and_scheduler_only(self):
        self.insert_episode()
        query_payload = {
            "query_type": "CURRENT_SETUP_QUERY",
            "token_id": self.token_id,
            "pair_id": self.pair_id,
            "query_at": self.now.isoformat(),
            "context": self.base_fingerprint(),
        }
        query_id, result = build_and_record_memory_retrieval_report(self.db_path, query_payload, self.now)
        self.assertGreater(query_id, 0)
        self.assertEqual(result["retrieval_result_label"], RetrievalResultLabel.RETRIEVAL_HAS_CLEAN_MATCHES.value)
        self.assertEqual(self.count_rows("printer_memory_retrieval_queries"), 1)
        self.assertGreater(self.count_rows("printer_memory_retrieval_matches"), 0)
        job_result, job_id = enqueue_memory_retrieval_job(self.db_path, self.token_id, self.pair_id, self.now + timedelta(minutes=1), reason="phase15_test")
        self.assertEqual(job_result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            running = connection.execute("SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?", (JobStatus.RUNNING.value,)).fetchone()[0]
        self.assertEqual(running, 0)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)
        self.assertEqual(self.count_rows("printer_token_lifecycle_events"), 0)

    def test_no_network_source_adapter_runtime_or_forbidden_concepts(self):
        source_text = "\n".join(inspect.getsource(module) for module in (fingerprint_builder, matcher, query, recorder, reports, retriever))
        for fragment in ("requests.get", "requests.post", "httpx", "aiohttp", "urllib.request", "while True", "APScheduler"):
            self.assertNotIn(fragment, source_text)
        names = []
        for module in (fingerprint_builder, matcher, query, recorder, reports, retriever):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        self.assertFalse(any(fragment in " ".join(names) for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()
