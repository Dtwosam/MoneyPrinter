"""
Post-RC Lane 8A — Paper Decision Unlock Review, WAIT/AVOID/NO_ACTION First

Tests prove:
- command requires --operator-approved
- command prints JSON output
- help text works without crashing
- report_only is true
- clean memory candidates from Lane 7 eligibility policy can support review readiness
- eligible clean memory window IDs (19/21/23 style) appear correctly when seeded
- WAIT review is ready from clean memory
- AVOID review is ready from clean memory
- NO_ACTION review is always ready (even with 0 clean memory)
- BUY remains locked
- SELL remains blocked (no open positions)
- HOLD remains blocked (no open positions)
- paper_decision_delta is 0
- paper_position_delta is 0
- paper_trade_event_delta is 0
- paper_trade_audit_delta is 0
- no paper decision rows are created
- no paper position rows are created
- no trade event rows are created
- no paper trade audit rows are created
- no PnL unlock occurs
- dirty memory is not used in readiness
- AUDIT_ONLY memory is not used
- do_not_train memory is not used
- MISSING_CRITICAL_DATA memory is not used
- WINDOW_5M_MICRO_EVENT does not qualify as main decision memory
- no scoring/ranking/confidence/weighted/embedding/vector logic is introduced
- command name and lane label are correct
- pyproject.toml registers the entry point
"""

import argparse
import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from typing import Iterator
from unittest.mock import patch

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    build_wait_avoid_no_action_readiness_payload,
    main_review_wait_avoid_no_action_readiness_once,
)


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class Lane8AWaitAvoidNoActionReadinessTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "lane8a.sqlite3"
        apply_migrations(self.db_path)
        self._seed_tokens_and_pairs()

    def tearDown(self) -> None:
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
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO printer_tokens (id, token_mint, chain, symbol, name)"
                " VALUES (10, 'test-mint-lane8a', 'solana', 'L8T', 'Lane8AToken')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex)"
                " VALUES (10, 10, 'test-pair-lane8a', 'raydium')"
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

    def _run_review(self) -> dict:
        return build_wait_avoid_no_action_readiness_payload(self.args())

    # ------------------------------------------------------------------
    # Operator approval gate
    # ------------------------------------------------------------------

    def test_requires_operator_approved(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            build_wait_avoid_no_action_readiness_payload(
                self.args(operator_approved=False)
            )
        self.assertIn("operator approval", str(ctx.exception).lower())

    def test_requires_solana_chain(self) -> None:
        with self.assertRaises(ValueError):
            build_wait_avoid_no_action_readiness_payload(
                self.args(chain="ethereum")
            )

    # ------------------------------------------------------------------
    # Help text and entry point
    # ------------------------------------------------------------------

    def test_help_text_works(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main_review_wait_avoid_no_action_readiness_once(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_main_entry_point_exits_0(self) -> None:
        result = main_review_wait_avoid_no_action_readiness_once(
            [
                "--operator-approved",
                "--db-path", str(self.db_path),
                "--project-root", str(PROJECT_ROOT),
            ]
        )
        self.assertEqual(result, 0)

    def test_main_entry_point_prints_json_to_stdout(self) -> None:
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            main_review_wait_avoid_no_action_readiness_once(
                [
                    "--operator-approved",
                    "--db-path", str(self.db_path),
                    "--project-root", str(PROJECT_ROOT),
                ]
            )
        output = buf.getvalue()
        self.assertTrue(output.strip(), "Expected JSON output on stdout")
        parsed = json.loads(output)
        self.assertIsInstance(parsed, dict)

    def test_command_exists_in_pyproject(self) -> None:
        pyproject = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-review-wait-avoid-no-action-readiness-once", pyproject)
        self.assertIn(
            "main_review_wait_avoid_no_action_readiness_once", pyproject
        )

    # ------------------------------------------------------------------
    # Lane/command identity
    # ------------------------------------------------------------------

    def test_command_name_is_correct(self) -> None:
        payload = self._run_review()
        self.assertEqual(
            payload["command"],
            "printer-review-wait-avoid-no-action-readiness-once",
        )

    def test_lane_label_is_correct(self) -> None:
        payload = self._run_review()
        self.assertEqual(payload["lane"], "post_rc_lane8a")
        self.assertEqual(
            payload["lane_label"],
            "PAPER_DECISION_UNLOCK_REVIEW_WAIT_AVOID_NO_ACTION_FIRST",
        )

    def test_report_only_is_true(self) -> None:
        payload = self._run_review()
        self.assertTrue(payload["report_only"])

    def test_operator_approved_is_true(self) -> None:
        payload = self._run_review()
        self.assertTrue(payload["operator_approved"])

    def test_chain_is_solana(self) -> None:
        payload = self._run_review()
        self.assertEqual(payload["chain"], "solana")

    # ------------------------------------------------------------------
    # Empty DB — NO_ACTION readiness only
    # ------------------------------------------------------------------

    def test_empty_db_gives_no_action_only(self) -> None:
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertFalse(payload["wait_review_ready"])
        self.assertFalse(payload["avoid_review_ready"])
        self.assertTrue(payload["no_action_review_ready"])
        self.assertFalse(payload["conservative_actions_review_ready"])
        self.assertEqual(payload["readiness_label"], "NO_ACTION_REVIEW_READY")

    def test_no_action_review_ready_always_true(self) -> None:
        # Even with 0 clean memory, NO_ACTION is always valid
        payload = self._run_review()
        self.assertTrue(payload["no_action_review_ready"])

    # ------------------------------------------------------------------
    # With clean memory — full conservative readiness
    # ------------------------------------------------------------------

    def test_clean_memory_gives_full_conservative_readiness(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 1)
        self.assertTrue(payload["wait_review_ready"])
        self.assertTrue(payload["avoid_review_ready"])
        self.assertTrue(payload["no_action_review_ready"])
        self.assertTrue(payload["conservative_actions_review_ready"])
        self.assertEqual(payload["readiness_label"], "WAIT_AVOID_NO_ACTION_REVIEW_READY")

    def test_wait_review_ready_from_clean_memory(self) -> None:
        self._insert_memory_window(window_id=19)
        payload = self._run_review()
        self.assertTrue(payload["wait_review_ready"])

    def test_avoid_review_ready_from_clean_memory(self) -> None:
        self._insert_memory_window(window_id=21)
        payload = self._run_review()
        self.assertTrue(payload["avoid_review_ready"])

    def test_eligible_window_ids_19_21_23_style(self) -> None:
        for wid in [19, 21, 23]:
            self._insert_memory_window(window_id=wid)
        payload = self._run_review()
        ids = payload["eligible_clean_memory_window_ids"]
        self.assertIn(19, ids)
        self.assertIn(21, ids)
        self.assertIn(23, ids)
        self.assertEqual(payload["clean_memory_candidates_count"], 3)

    def test_readiness_reasons_mention_buy_locked(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        reasons_str = " ".join(payload["readiness_reasons"])
        self.assertIn("BUY", reasons_str)
        self.assertIn("locked", reasons_str.lower())

    # ------------------------------------------------------------------
    # Hard locks
    # ------------------------------------------------------------------

    def test_buy_unlock_is_false(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertFalse(payload["buy_unlock"])

    def test_position_unlock_is_false(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertFalse(payload["position_unlock"])

    def test_pnl_unlock_is_false(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertFalse(payload["pnl_unlock"])

    def test_buy_unlock_is_false_when_no_memory(self) -> None:
        payload = self._run_review()
        self.assertFalse(payload["buy_unlock"])

    # ------------------------------------------------------------------
    # Action boundary
    # ------------------------------------------------------------------

    def test_allowed_future_actions_are_only_conservative(self) -> None:
        payload = self._run_review()
        self.assertEqual(
            sorted(payload["allowed_future_review_actions"]),
            ["AVOID", "NO_ACTION", "WAIT"],
        )
        self.assertNotIn("BUY", payload["allowed_future_review_actions"])
        self.assertNotIn("SELL", payload["allowed_future_review_actions"])
        self.assertNotIn("HOLD", payload["allowed_future_review_actions"])

    def test_blocked_actions_contains_buy(self) -> None:
        payload = self._run_review()
        self.assertIn("BUY", payload["blocked_actions"])

    def test_sell_remains_blocked(self) -> None:
        payload = self._run_review()
        self.assertIn("SELL", payload["blocked_actions"])

    def test_hold_remains_blocked(self) -> None:
        payload = self._run_review()
        self.assertIn("HOLD", payload["blocked_actions"])

    # ------------------------------------------------------------------
    # Paper guard deltas — all zero
    # ------------------------------------------------------------------

    def test_paper_decision_delta_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_decision_delta"], 0)

    def test_paper_position_delta_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_position_delta"], 0)

    def test_paper_trade_event_delta_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_trade_event_delta"], 0)

    def test_paper_trade_audit_delta_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_trade_audit_delta"], 0)

    def test_paper_decisions_created_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_decisions_created"], 0)

    def test_paper_positions_created_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_positions_created"], 0)

    def test_paper_trade_events_created_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_trade_events_created"], 0)

    def test_paper_trade_audits_created_is_0(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertEqual(payload["paper_trade_audits_created"], 0)

    def test_guard_tables_unchanged(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["guard_table_deltas"], {})

    # ------------------------------------------------------------------
    # No paper rows are created in the DB
    # ------------------------------------------------------------------

    def test_no_paper_decision_rows_created(self) -> None:
        self._insert_memory_window(window_id=23)
        self._run_review()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_decisions"), 0)

    def test_no_paper_position_rows_created(self) -> None:
        self._insert_memory_window(window_id=23)
        self._run_review()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_positions"), 0)

    def test_no_trade_event_rows_created(self) -> None:
        self._insert_memory_window(window_id=23)
        self._run_review()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_trade_events"), 0)

    def test_no_paper_trade_audit_rows_created(self) -> None:
        self._insert_memory_window(window_id=23)
        self._run_review()
        with self._connect() as conn:
            self.assertEqual(count_rows(conn, "printer_paper_trade_audits"), 0)

    # ------------------------------------------------------------------
    # Memory eligibility exclusions (Lane 7 policy reused)
    # ------------------------------------------------------------------

    def test_dirty_memory_not_used_in_readiness(self) -> None:
        self._insert_memory_window(
            window_id=50,
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
            data_quality_label="DIRTY_DATA",
        )
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        ids = payload["eligible_clean_memory_window_ids"]
        self.assertNotIn(50, ids)
        self.assertFalse(payload["wait_review_ready"])
        self.assertFalse(payload["avoid_review_ready"])

    def test_audit_only_memory_not_used(self) -> None:
        self._insert_memory_window(
            window_id=51,
            memory_status="AUDIT_ONLY",
            memory_quality_label="AUDIT_ONLY_MEMORY",
        )
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_audit_only_count"], 1)
        self.assertNotIn(51, payload["eligible_clean_memory_window_ids"])

    def test_do_not_train_memory_not_used(self) -> None:
        self._insert_memory_window(
            window_id=52,
            do_not_train=1,
        )
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_do_not_train_count"], 1)
        self.assertNotIn(52, payload["eligible_clean_memory_window_ids"])

    def test_missing_critical_data_not_used(self) -> None:
        self._insert_memory_window(
            window_id=53,
            data_quality_label="MISSING_CRITICAL_DATA",
            memory_quality_label="DIRTY_MEMORY",
            memory_status="DIRTY_MEMORY",
        )
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_missing_critical_data_count"], 1)

    def test_5m_micro_event_does_not_qualify_as_main_decision_memory(self) -> None:
        self._insert_memory_window(
            window_id=54,
            window_kind="WINDOW_5M_MICRO_EVENT",
        )
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertEqual(payload["excluded_5m_micro_event_count"], 1)
        self.assertNotIn(54, payload["eligible_clean_memory_window_ids"])
        self.assertFalse(payload["wait_review_ready"])

    def test_partial_memory_is_excluded_from_readiness(self) -> None:
        self._insert_memory_window(
            window_id=55,
            memory_status="PARTIAL_MEMORY",
            memory_quality_label="PARTIAL_MEMORY",
        )
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 0)
        self.assertNotIn(55, payload["eligible_clean_memory_window_ids"])

    # ------------------------------------------------------------------
    # Mixed population
    # ------------------------------------------------------------------

    def test_mixed_population_only_clean_eligible(self) -> None:
        self._insert_memory_window(window_id=19)
        self._insert_memory_window(window_id=21)
        self._insert_memory_window(window_id=23)
        self._insert_memory_window(
            window_id=30,
            memory_status="AUDIT_ONLY",
            memory_quality_label="AUDIT_ONLY_MEMORY",
        )
        self._insert_memory_window(
            window_id=31,
            do_not_train=1,
        )
        self._insert_memory_window(
            window_id=32,
            window_kind="WINDOW_5M_MICRO_EVENT",
        )
        payload = self._run_review()
        self.assertEqual(payload["clean_memory_candidates_count"], 3)
        ids = payload["eligible_clean_memory_window_ids"]
        self.assertEqual(sorted(ids), [19, 21, 23])
        self.assertEqual(payload["excluded_audit_only_count"], 1)
        self.assertEqual(payload["excluded_do_not_train_count"], 1)
        self.assertEqual(payload["excluded_5m_micro_event_count"], 1)
        self.assertTrue(payload["wait_review_ready"])
        self.assertTrue(payload["avoid_review_ready"])
        self.assertTrue(payload["conservative_actions_review_ready"])
        self.assertEqual(payload["readiness_label"], "WAIT_AVOID_NO_ACTION_REVIEW_READY")

    # ------------------------------------------------------------------
    # Decision template field readiness
    # ------------------------------------------------------------------

    def test_decision_template_shows_no_eligible_when_empty(self) -> None:
        payload = self._run_review()
        tmpl = payload["decision_template_field_readiness"]
        self.assertEqual(
            tmpl["similar_clean_memories_found"], "MISSING_NO_ELIGIBLE_MEMORY"
        )
        self.assertEqual(
            tmpl["what_happened_in_those_memories"], "MISSING_NO_ELIGIBLE_MEMORY"
        )

    def test_decision_template_shows_count_when_eligible(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        tmpl = payload["decision_template_field_readiness"]
        self.assertEqual(tmpl["similar_clean_memories_found"], 1)
        self.assertIsInstance(tmpl["what_happened_in_those_memories"], list)

    def test_decision_template_current_context_fields_not_invented(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        tmpl = payload["decision_template_field_readiness"]
        # These require current token context — must not be invented
        for field in [
            "current_setup",
            "liquidity_exit_condition",
            "trading_flow_condition",
            "chart_volatility_condition",
        ]:
            self.assertIn("WILL_REQUIRE", tmpl[field])

    def test_decision_template_decision_time_fields_not_invented(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        tmpl = payload["decision_template_field_readiness"]
        for field in ["decision", "current_action", "reason",
                      "invalidation_condition", "paper_trade_status"]:
            self.assertIn("WILL_BE_SET", tmpl[field])

    # ------------------------------------------------------------------
    # No scoring/ranking/confidence/weighted/embedding/vector
    # ------------------------------------------------------------------

    def test_no_scoring_fields_in_output(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        payload_str = json.dumps(payload)
        for forbidden in ["score", "rank", "confidence", "weighted",
                          "embed", "vector"]:
            self.assertNotIn(forbidden, payload_str.lower(),
                             f"Forbidden term '{forbidden}' found in output")

    def test_no_scoring_in_readiness_reasons(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        reasons_str = " ".join(payload["readiness_reasons"]).lower()
        for forbidden in ["score", "rank", "confidence", "weighted", "embed"]:
            self.assertNotIn(forbidden, reasons_str)

    # ------------------------------------------------------------------
    # No PnL fields created
    # ------------------------------------------------------------------

    def test_pnl_fields_are_false_locks(self) -> None:
        self._insert_memory_window(window_id=23)
        payload = self._run_review()
        self.assertFalse(payload["pnl_unlock"])
        # pnl must not be a non-false value
        pnl_val = payload.get("pnl_unlock")
        self.assertIs(pnl_val, False)


if __name__ == "__main__":
    unittest.main()
