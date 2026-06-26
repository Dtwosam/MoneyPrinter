"""
Post-RC Lane 7 — Controlled Clean-Memory Retrieval Reporting

Tests prove:
- CLEAN_MEMORY + CLEAN_DATA + do_not_train=0 + WINDOW_CLOSED is eligible.
- AUDIT_ONLY is excluded.
- MISSING_CRITICAL_DATA is excluded.
- do_not_train=1 is excluded.
- WINDOW_5M_MICRO_EVENT cannot unlock retrieval by itself.
- Report includes memory_window_id-style clean memory eligibility.
- No paper decisions are created.
- No paper positions are created.
- No paper trade events are created.
- No paper trade audits are created.
- No BUY/PnL unlock is possible.
- Dirty memory never appears in retrieval results.
- No scoring/ranking/confidence/weighted retrieval logic is introduced.
"""

import argparse
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from typing import Iterator

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    build_clean_memory_retrieval_report_once_payload,
    main_build_clean_memory_retrieval_report_once,
)


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class Lane7CleanMemoryRetrievalReportTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "lane7.sqlite3"
        apply_migrations(self.db_path)
        self._seed_tokens_and_pairs()

    def tearDown(self) -> None:
        # tempdir cleanup is robust even if files are open on Windows
        try:
            self.tempdir.cleanup()
        except Exception:
            pass

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def args(self, **overrides: object) -> argparse.Namespace:
        defaults = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "chain": "solana",
        }
        defaults.update(overrides)
        return argparse.Namespace(**defaults)

    # ------------------------------------------------------------------
    # Fixture helpers
    # ------------------------------------------------------------------

    def _seed_tokens_and_pairs(self) -> None:
        # printer_tokens columns: id, token_mint, chain, symbol, name,
        #   first_seen_at, last_seen_at, token_status, created_at, updated_at
        # printer_pairs columns: id, token_id, pair_address, dex, pool_source,
        #   base_token_mint, quote_token_mint, first_seen_at, last_seen_at,
        #   created_at, updated_at
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO printer_tokens (id, token_mint, chain, symbol, name)
                VALUES (10, 'test-mint-lane7', 'solana', 'L7T', 'Lane7Token')
                """
            )
            conn.execute(
                """
                INSERT INTO printer_pairs (id, token_id, pair_address, dex)
                VALUES (10, 10, 'test-pair-lane7', 'raydium')
                """
            )

    def _insert_memory_window(
        self,
        *,
        window_id: int,
        memory_status: str = "CLEAN_MEMORY",
        memory_quality_label: str = "CLEAN_MEMORY",
        data_quality_label: str = "CLEAN_DATA",
        do_not_train: int = 0,
        window_status: str = "WINDOW_CLOSED",
        window_kind: str = "WINDOW_15M",
        outcome_label: str = "CONSOLIDATION",
        token_id: int = 10,
        pair_id: int = 10,
        supporting_context_json: str | None = None,
        source_reference: str | None = None,
        evidence_identity_hash: str | None = None,
        snapshot_start_id: int | None = None,
        snapshot_end_id: int | None = None,
    ) -> None:
        ctx = supporting_context_json or json.dumps({"context_labels": {}})
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO printer_memory_windows (
                    id, token_id, pair_id, window_kind,
                    opened_at, closed_at,
                    memory_status, data_quality_label, do_not_train,
                    window_status, outcome_label, memory_quality_label,
                    rejection_reasons_json, supporting_context_json,
                    created_by_phase,
                    snapshot_start_id, snapshot_end_id,
                    source_reference, evidence_identity_hash,
                    duplicate_guard_status
                ) VALUES (
                    ?, ?, ?, ?,
                    datetime('now'), datetime('now'),
                    ?, ?, ?,
                    ?, ?, ?,
                    '[]', ?,
                    'test',
                    ?, ?,
                    ?, ?,
                    'NEW_DISTINCT_EVIDENCE_WINDOW'
                )
                """,
                (
                    window_id, token_id, pair_id, window_kind,
                    memory_status, data_quality_label, do_not_train,
                    window_status, outcome_label, memory_quality_label,
                    ctx,
                    snapshot_start_id, snapshot_end_id,
                    source_reference or f"ref-{window_id}",
                    evidence_identity_hash or f"hash-{window_id}",
                ),
            )

    def _run_report(self) -> dict:
        return build_clean_memory_retrieval_report_once_payload(self.args())

    # ------------------------------------------------------------------
    # Core eligibility tests
    # ------------------------------------------------------------------

    def test_clean_memory_clean_data_do_not_train_0_is_eligible(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 1)
        eligible = payload["retrieval_report"]["eligible_clean_memories"]
        self.assertEqual(len(eligible), 1)
        self.assertEqual(eligible[0]["memory_window_id"], 23)
        self.assertTrue(eligible[0]["retrieval_eligible"])
        self.assertIsNone(eligible[0]["exclusion_reason"])

    def test_audit_only_memory_status_is_excluded(self) -> None:
        self._insert_memory_window(
            window_id=31,
            memory_status="AUDIT_ONLY",
            memory_quality_label="AUDIT_ONLY_MEMORY",
        )
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_audit_only_count"], 1)
        report = payload["retrieval_report"]
        self.assertIn(31, report["excluded_audit_only_window_ids"])
        for mem in report["eligible_clean_memories"]:
            self.assertNotEqual(mem["memory_window_id"], 31)

    def test_audit_only_memory_quality_label_excludes_even_if_status_differs(self) -> None:
        # AUDIT_ONLY via memory_quality_label even if memory_status is PARTIAL_MEMORY
        self._insert_memory_window(
            window_id=32,
            memory_status="PARTIAL_MEMORY",
            memory_quality_label="AUDIT_ONLY_MEMORY",
        )
        payload = self._run_report()
        self.assertEqual(payload["excluded_audit_only_count"], 1)
        self.assertIn(32, payload["retrieval_report"]["excluded_audit_only_window_ids"])

    def test_missing_critical_data_is_excluded(self) -> None:
        self._insert_memory_window(
            window_id=40,
            data_quality_label="MISSING_CRITICAL_DATA",
            memory_quality_label="DIRTY_MEMORY",
            memory_status="DIRTY_MEMORY",
        )
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_missing_critical_data_count"], 1)
        self.assertIn(
            40,
            payload["retrieval_report"]["excluded_missing_critical_data_window_ids"],
        )

    def test_do_not_train_1_is_excluded(self) -> None:
        self._insert_memory_window(
            window_id=50,
            do_not_train=1,
            memory_status="DO_NOT_TRAIN",
            memory_quality_label="DO_NOT_TRAIN_MEMORY",
        )
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_do_not_train_count"], 1)
        self.assertIn(50, payload["retrieval_report"]["excluded_do_not_train_window_ids"])

    def test_window_5m_micro_event_cannot_unlock_retrieval_by_itself(self) -> None:
        # Even if all quality fields are clean, 5m cannot unlock retrieval
        self._insert_memory_window(
            window_id=60,
            window_kind="WINDOW_5M_MICRO_EVENT",
            memory_status="CLEAN_MEMORY",
            memory_quality_label="CLEAN_MEMORY",
            data_quality_label="CLEAN_DATA",
            do_not_train=0,
            window_status="WINDOW_CLOSED",
        )
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_5m_micro_event_count"], 1)
        self.assertIn(60, payload["retrieval_report"]["excluded_5m_micro_event_window_ids"])
        for mem in payload["retrieval_report"]["eligible_clean_memories"]:
            self.assertNotEqual(mem["memory_window_id"], 60)

    def test_dirty_memory_never_appears_in_retrieval_results(self) -> None:
        self._insert_memory_window(
            window_id=70,
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
            data_quality_label="DIRTY_DATA",
        )
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        for mem in payload["retrieval_report"]["eligible_clean_memories"]:
            self.assertNotEqual(mem["memory_window_id"], 70)

    def test_partial_memory_is_excluded_from_clean_eligibility(self) -> None:
        self._insert_memory_window(
            window_id=80,
            memory_status="PARTIAL_MEMORY",
            memory_quality_label="PARTIAL_MEMORY",
            data_quality_label="CLEAN_DATA",
        )
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        for mem in payload["retrieval_report"]["eligible_clean_memories"]:
            self.assertNotEqual(mem["memory_window_id"], 80)

    def test_window_not_closed_is_excluded(self) -> None:
        self._insert_memory_window(
            window_id=90,
            memory_status="CLEAN_MEMORY",
            memory_quality_label="CLEAN_MEMORY",
            data_quality_label="CLEAN_DATA",
            do_not_train=0,
            window_status="WINDOW_OPEN",
        )
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)

    # ------------------------------------------------------------------
    # memory_window_id 23 style clean memory eligibility
    # ------------------------------------------------------------------

    def test_report_includes_memory_window_id_23_style_clean_eligibility(self) -> None:
        ctx = json.dumps({
            "context_labels": {
                "market_regime_label": "RISK_ON",
                "chain_heat_label": "SOLANA_WARM",
                "safety_status_label": "SAFETY_CLEAR",
            }
        })
        self._insert_memory_window(
            window_id=23,
            memory_status="CLEAN_MEMORY",
            memory_quality_label="CLEAN_MEMORY",
            data_quality_label="CLEAN_DATA",
            do_not_train=0,
            window_status="WINDOW_CLOSED",
            window_kind="WINDOW_15M",
            outcome_label="CONSOLIDATION",
            supporting_context_json=ctx,
        )
        payload = self._run_report()
        eligible = payload["retrieval_report"]["eligible_clean_memories"]
        self.assertEqual(len(eligible), 1)
        row = eligible[0]
        self.assertEqual(row["memory_window_id"], 23)
        self.assertEqual(row["window_kind"], "WINDOW_15M")
        self.assertEqual(row["outcome_label"], "CONSOLIDATION")
        self.assertTrue(row["retrieval_eligible"])
        self.assertEqual(row["market_regime_label"], "RISK_ON")
        self.assertEqual(row["chain_heat_label"], "SOLANA_WARM")
        self.assertEqual(row["safety_status_label"], "SAFETY_CLEAR")

    # ------------------------------------------------------------------
    # Mixed population
    # ------------------------------------------------------------------

    def test_mixed_population_counts_are_correct(self) -> None:
        self._insert_memory_window(window_id=100)  # eligible clean
        self._insert_memory_window(
            window_id=101,
            memory_status="AUDIT_ONLY",
            memory_quality_label="AUDIT_ONLY_MEMORY",
        )
        self._insert_memory_window(
            window_id=102,
            do_not_train=1,
            memory_status="DO_NOT_TRAIN",
            memory_quality_label="DO_NOT_TRAIN_MEMORY",
        )
        self._insert_memory_window(
            window_id=103,
            data_quality_label="MISSING_CRITICAL_DATA",
            memory_quality_label="DIRTY_MEMORY",
            memory_status="DIRTY_MEMORY",
        )
        self._insert_memory_window(
            window_id=104,
            window_kind="WINDOW_5M_MICRO_EVENT",
        )
        self._insert_memory_window(
            window_id=105,
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
            data_quality_label="DIRTY_DATA",
        )

        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 1)
        self.assertEqual(payload["excluded_audit_only_count"], 1)
        self.assertEqual(payload["excluded_do_not_train_count"], 1)
        self.assertEqual(payload["excluded_missing_critical_data_count"], 1)
        self.assertEqual(payload["excluded_5m_micro_event_count"], 1)
        self.assertEqual(payload["excluded_dirty_memory_count"], 1)

    # ------------------------------------------------------------------
    # Paper row guard tests
    # ------------------------------------------------------------------

    def test_no_paper_decisions_are_created(self) -> None:
        self._insert_memory_window(window_id=200)
        self._run_report()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_decisions"), 0)

    def test_no_paper_positions_are_created(self) -> None:
        self._insert_memory_window(window_id=201)
        self._run_report()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_positions"), 0)

    def test_no_paper_trade_events_are_created(self) -> None:
        self._insert_memory_window(window_id=202)
        self._run_report()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_trade_events"), 0)

    def test_no_paper_trade_audits_are_created(self) -> None:
        self._insert_memory_window(window_id=203)
        self._run_report()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_trade_audits"), 0)

    def test_buy_unlock_is_false(self) -> None:
        self._insert_memory_window(window_id=210)
        payload = self._run_report()
        self.assertFalse(payload["buy_unlock"])

    def test_pnl_unlock_is_false(self) -> None:
        self._insert_memory_window(window_id=211)
        payload = self._run_report()
        self.assertFalse(payload["pnl_unlock"])

    def test_paper_decision_delta_is_zero(self) -> None:
        self._insert_memory_window(window_id=212)
        payload = self._run_report()
        self.assertEqual(payload["paper_decision_delta"], 0)

    def test_paper_position_delta_is_zero(self) -> None:
        self._insert_memory_window(window_id=213)
        payload = self._run_report()
        self.assertEqual(payload["paper_position_delta"], 0)

    def test_paper_trade_event_delta_is_zero(self) -> None:
        self._insert_memory_window(window_id=214)
        payload = self._run_report()
        self.assertEqual(payload["paper_trade_event_delta"], 0)

    def test_paper_trade_audit_delta_is_zero(self) -> None:
        self._insert_memory_window(window_id=215)
        payload = self._run_report()
        self.assertEqual(payload["paper_trade_audit_delta"], 0)

    # ------------------------------------------------------------------
    # Report-only / no writes
    # ------------------------------------------------------------------

    def test_retrieval_matches_created_is_zero(self) -> None:
        self._insert_memory_window(window_id=220)
        payload = self._run_report()
        self.assertEqual(payload["retrieval_matches_created"], 0)

    def test_report_only_flag_is_set(self) -> None:
        payload = self._run_report()
        self.assertTrue(payload["report_only"])

    def test_guard_tables_unchanged(self) -> None:
        self._insert_memory_window(window_id=230)
        payload = self._run_report()
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["guard_table_deltas"], {})

    def test_no_retrieval_query_rows_written(self) -> None:
        self._insert_memory_window(window_id=240)
        self._run_report()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_memory_retrieval_queries"), 0)
            self.assertEqual(count_rows(conn, "printer_memory_retrieval_matches"), 0)

    def test_no_source_governor_bypass(self) -> None:
        self._insert_memory_window(window_id=250)
        self._run_report()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_source_requests"), 0)
            self.assertEqual(count_rows(conn, "printer_source_responses"), 0)

    # ------------------------------------------------------------------
    # No scoring/ranking/confidence/weighted logic
    # ------------------------------------------------------------------

    def test_no_scoring_fields_in_eligible_row(self) -> None:
        self._insert_memory_window(window_id=300)
        payload = self._run_report()
        eligible = payload["retrieval_report"]["eligible_clean_memories"]
        self.assertEqual(len(eligible), 1)
        row = eligible[0]
        forbidden = {
            "score", "rank", "confidence", "weight", "similarity_score",
            "match_score", "weighted_match", "ranking",
        }
        for field in forbidden:
            self.assertNotIn(field, row, f"Forbidden scoring field present: {field}")

    def test_no_scoring_fields_in_top_level_payload(self) -> None:
        self._insert_memory_window(window_id=301)
        payload = self._run_report()
        forbidden = {
            "score", "rank", "confidence", "weight", "similarity_score",
            "match_score", "weighted_match", "ranking",
        }
        for key in forbidden:
            self.assertNotIn(key, payload, f"Forbidden scoring key at top level: {key}")

    # ------------------------------------------------------------------
    # Operator-approval gate
    # ------------------------------------------------------------------

    def test_requires_operator_approved(self) -> None:
        with self.assertRaises(ValueError):
            build_clean_memory_retrieval_report_once_payload(
                self.args(operator_approved=False)
            )

    def test_requires_solana_chain(self) -> None:
        with self.assertRaises(ValueError):
            build_clean_memory_retrieval_report_once_payload(
                self.args(chain="ethereum")
            )

    # ------------------------------------------------------------------
    # Command metadata
    # ------------------------------------------------------------------

    def test_command_name_is_correct(self) -> None:
        payload = self._run_report()
        self.assertEqual(
            payload["command"],
            "printer-build-clean-memory-retrieval-report-once",
        )

    def test_lane_label_is_correct(self) -> None:
        payload = self._run_report()
        self.assertEqual(payload["lane"], "post_rc_lane7")
        self.assertEqual(payload["lane_label"], "CONTROLLED_CLEAN_MEMORY_RETRIEVAL_REPORTING")

    def test_main_entry_point_returns_zero_exit_code(self) -> None:
        code = main_build_clean_memory_retrieval_report_once([
            "--db-path", str(self.db_path),
            "--project-root", str(PROJECT_ROOT),
            "--operator-approved",
            "--chain", "solana",
        ])
        self.assertEqual(code, 0)

    def test_main_entry_point_returns_nonzero_without_approval(self) -> None:
        code = main_build_clean_memory_retrieval_report_once([
            "--db-path", str(self.db_path),
            "--project-root", str(PROJECT_ROOT),
            "--chain", "solana",
        ])
        self.assertNotEqual(code, 0)

    # ------------------------------------------------------------------
    # Empty DB baseline
    # ------------------------------------------------------------------

    def test_empty_db_returns_zero_candidates(self) -> None:
        payload = self._run_report()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(
            payload["retrieval_report"]["total_memory_window_count"], 0
        )
        self.assertFalse(payload["buy_unlock"])
        self.assertFalse(payload["pnl_unlock"])


if __name__ == "__main__":
    unittest.main()
