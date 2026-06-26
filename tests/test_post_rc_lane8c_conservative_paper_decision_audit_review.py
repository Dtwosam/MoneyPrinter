"""
Post-RC Lane 8C — Conservative Paper Decision Audit Review

Tests prove:
- command requires --operator-approved
- --help works without crashing
- missing/nonexistent paper_decision_id is rejected (audit FAILED)
- WAIT decision with clean memory passes review (audit PASSED)
- AVOID decision with clean memory passes review
- NO_ACTION decision with clean memory passes review
- BUY decision seeded manually fails review (not conservative)
- SELL decision seeded manually fails review
- HOLD decision seeded manually fails review
- decision with dirty memory backing fails review
- decision with AUDIT_ONLY memory_status backing fails review
- decision with AUDIT_ONLY_MEMORY memory_quality_label backing fails review
- decision with do_not_train=1 backing fails review
- decision with MISSING_CRITICAL_DATA backing fails review
- decision backed by WINDOW_5M_MICRO_EVENT fails review
- decision with no memory_window_id (null) fails review
- decision with dirty data quality (not CLEAN_DATA) fails review
- decision with non-COMPLETE source_status fails review
- no paper position rows created
- no paper trade event rows created
- no paper trade audit rows created
- no PnL output except false locks
- buy_unlock is always false
- position_unlock is always false
- pnl_unlock is always false
- paper_position_delta is 0
- paper_trade_event_delta is 0
- paper_trade_audit_delta is 0
- guard_tables_unchanged is true (report-only, no writes)
- report_only is true
- review_rows_created is 0
- command name and lane label correct
- pyproject.toml registers the entry point
- main entry point exits 0
- main prints JSON to stdout
- no scoring/ranking/confidence/weighted/embedding/vector logic
- blocked_actions includes BUY, SELL, HOLD
- paper_position_count_for_decision is 0 when no positions exist
- audit_review_status is PASSED when all checks pass
- audit_review_status is FAILED when any check fails
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
    build_conservative_paper_decision_audit_review_payload,
    main_review_conservative_paper_decision_once,
)


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class Lane8CAuditReviewTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "lane8c.sqlite3"
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
            "paper_decision_id": 1,
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
                " VALUES (10, 'test-mint-lane8c', 'solana', 'L8C', 'Lane8CToken')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex)"
                " VALUES (10, 10, 'test-pair-lane8c', 'raydium')"
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
    ) -> None:
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
                    '[]', '{"context_labels": {}}',
                    'test',
                    NULL, NULL,
                    ?, ?,
                    'NEW_DISTINCT_EVIDENCE_WINDOW'
                )
                """,
                (
                    window_id, token_id, pair_id, window_kind,
                    memory_status, data_quality_label, do_not_train,
                    window_status, outcome_label, memory_quality_label,
                    f"ref-{window_id}", f"hash-{window_id}",
                ),
            )

    def _insert_paper_decision(
        self,
        *,
        decision_id: int,
        decision_action: str = "WAIT",
        decision_status: str = "PAPER_DECISION_PROPOSED",
        memory_window_id: int | None = 23,
        source_status: str = "COMPLETE",
        data_quality_label: str = "CLEAN_DATA",
        token_id: int = 10,
        pair_id: int = 10,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO printer_paper_decisions (
                    id, token_id, pair_id,
                    decision_action, decision_status,
                    memory_window_id,
                    source_status, data_quality_label
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision_id, token_id, pair_id,
                    decision_action, decision_status,
                    memory_window_id,
                    source_status, data_quality_label,
                ),
            )

    def _seed_clean_decision(
        self,
        decision_id: int = 1,
        decision_action: str = "WAIT",
        window_id: int = 23,
    ) -> None:
        self._insert_memory_window(window_id=window_id)
        self._insert_paper_decision(
            decision_id=decision_id,
            decision_action=decision_action,
            memory_window_id=window_id,
        )

    def _count_paper_decisions(self) -> int:
        with self._connect() as conn:
            return count_rows(conn, "printer_paper_decisions")

    def _count_paper_positions(self) -> int:
        with self._connect() as conn:
            return count_rows(conn, "printer_paper_positions")

    def _count_paper_trade_events(self) -> int:
        with self._connect() as conn:
            return count_rows(conn, "printer_paper_trade_events")

    def _count_paper_trade_audits(self) -> int:
        with self._connect() as conn:
            return count_rows(conn, "printer_paper_trade_audits")

    # ------------------------------------------------------------------
    # Operator approval gate
    # ------------------------------------------------------------------

    def test_requires_operator_approved(self) -> None:
        self._seed_clean_decision()
        with self.assertRaises(ValueError) as ctx:
            build_conservative_paper_decision_audit_review_payload(
                self.args(operator_approved=False)
            )
        self.assertIn("operator approval", str(ctx.exception).lower())

    def test_requires_solana_chain(self) -> None:
        self._seed_clean_decision()
        with self.assertRaises(ValueError):
            build_conservative_paper_decision_audit_review_payload(
                self.args(chain="ethereum")
            )

    # ------------------------------------------------------------------
    # Help text and entry point
    # ------------------------------------------------------------------

    def test_help_text_works(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main_review_conservative_paper_decision_once(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_main_entry_point_exits_0(self) -> None:
        self._seed_clean_decision()
        result = main_review_conservative_paper_decision_once(
            [
                "--operator-approved",
                "--paper-decision-id", "1",
                "--db-path", str(self.db_path),
                "--project-root", str(PROJECT_ROOT),
            ]
        )
        self.assertEqual(result, 0)

    def test_main_prints_json_to_stdout(self) -> None:
        self._seed_clean_decision()
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            main_review_conservative_paper_decision_once(
                [
                    "--operator-approved",
                    "--paper-decision-id", "1",
                    "--db-path", str(self.db_path),
                    "--project-root", str(PROJECT_ROOT),
                ]
            )
        output = buf.getvalue()
        self.assertGreater(len(output), 0)
        parsed = json.loads(output)
        self.assertIn("audit_review_status", parsed)

    def test_pyproject_registers_entry_point(self) -> None:
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        self.assertIn("printer-review-conservative-paper-decision-once", content)
        self.assertIn("main_review_conservative_paper_decision_once", content)

    # ------------------------------------------------------------------
    # Decision not found
    # ------------------------------------------------------------------

    def test_nonexistent_decision_id_returns_failed(self) -> None:
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=9999)
        )
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["conservative_action_valid"])
        self.assertFalse(payload["clean_memory_backed"])
        any_reason_mentions_not_found = any(
            "not_found" in r.lower() or "9999" in r
            for r in payload["audit_review_reasons"]
        )
        self.assertTrue(any_reason_mentions_not_found)

    def test_nonexistent_decision_no_writes(self) -> None:
        before = self._count_paper_decisions()
        build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=9999)
        )
        self.assertEqual(self._count_paper_decisions(), before)

    def test_nonexistent_decision_guard_tables_unchanged(self) -> None:
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=9999)
        )
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["guard_table_deltas"], {})

    # ------------------------------------------------------------------
    # WAIT / AVOID / NO_ACTION — clean decisions pass review
    # ------------------------------------------------------------------

    def test_wait_clean_decision_passes(self) -> None:
        self._seed_clean_decision(decision_action="WAIT")
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "PASSED")
        self.assertTrue(payload["conservative_action_valid"])
        self.assertTrue(payload["clean_memory_backed"])
        self.assertTrue(payload["memory_window_retrieval_eligible"])
        self.assertEqual(payload["decision_action"], "WAIT")

    def test_avoid_clean_decision_passes(self) -> None:
        self._seed_clean_decision(decision_id=2, decision_action="AVOID", window_id=24)
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=2)
        )
        self.assertEqual(payload["audit_review_status"], "PASSED")
        self.assertEqual(payload["decision_action"], "AVOID")

    def test_no_action_clean_decision_passes(self) -> None:
        self._seed_clean_decision(decision_id=3, decision_action="NO_ACTION", window_id=25)
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=3)
        )
        self.assertEqual(payload["audit_review_status"], "PASSED")
        self.assertEqual(payload["decision_action"], "NO_ACTION")

    # ------------------------------------------------------------------
    # BUY / SELL / HOLD — non-conservative decisions fail review
    # ------------------------------------------------------------------

    def test_buy_decision_fails_review(self) -> None:
        self._insert_memory_window(window_id=23)
        self._insert_paper_decision(
            decision_id=1,
            decision_action="BUY",
            memory_window_id=23,
        )
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["conservative_action_valid"])
        any_reason_mentions_buy = any("BUY" in r for r in payload["audit_review_reasons"])
        self.assertTrue(any_reason_mentions_buy)

    def test_sell_decision_fails_review(self) -> None:
        self._insert_memory_window(window_id=23)
        self._insert_paper_decision(
            decision_id=1, decision_action="SELL", memory_window_id=23
        )
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["conservative_action_valid"])

    def test_hold_decision_fails_review(self) -> None:
        self._insert_memory_window(window_id=23)
        self._insert_paper_decision(
            decision_id=1, decision_action="HOLD", memory_window_id=23
        )
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["conservative_action_valid"])

    # ------------------------------------------------------------------
    # Memory window eligibility failures
    # ------------------------------------------------------------------

    def test_dirty_memory_backing_fails(self) -> None:
        self._insert_memory_window(
            window_id=23,
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
        )
        self._insert_paper_decision(decision_id=1, decision_action="WAIT", memory_window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])
        self.assertFalse(payload["memory_window_retrieval_eligible"])

    def test_audit_only_memory_status_backing_fails(self) -> None:
        self._insert_memory_window(
            window_id=23,
            memory_status="AUDIT_ONLY",
            memory_quality_label="CLEAN_MEMORY",
        )
        self._insert_paper_decision(decision_id=1, decision_action="WAIT", memory_window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])
        any_reason = any("AUDIT_ONLY" in r for r in payload["audit_review_reasons"])
        self.assertTrue(any_reason)

    def test_audit_only_memory_quality_label_backing_fails(self) -> None:
        self._insert_memory_window(
            window_id=23,
            memory_status="CLEAN_MEMORY",
            memory_quality_label="AUDIT_ONLY_MEMORY",
        )
        self._insert_paper_decision(decision_id=1, decision_action="WAIT", memory_window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])

    def test_do_not_train_backing_fails(self) -> None:
        self._insert_memory_window(window_id=23, do_not_train=1)
        self._insert_paper_decision(decision_id=1, decision_action="WAIT", memory_window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])
        any_reason = any("do_not_train" in r for r in payload["audit_review_reasons"])
        self.assertTrue(any_reason)

    def test_missing_critical_data_backing_fails(self) -> None:
        self._insert_memory_window(window_id=23, data_quality_label="MISSING_CRITICAL_DATA")
        self._insert_paper_decision(decision_id=1, decision_action="WAIT", memory_window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])

    def test_5m_micro_event_backing_fails(self) -> None:
        self._insert_memory_window(window_id=23, window_kind="WINDOW_5M_MICRO_EVENT")
        self._insert_paper_decision(decision_id=1, decision_action="WAIT", memory_window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])
        any_reason = any("5M_MICRO_EVENT" in r for r in payload["audit_review_reasons"])
        self.assertTrue(any_reason)

    def test_null_memory_window_id_fails(self) -> None:
        self._insert_paper_decision(
            decision_id=1,
            decision_action="WAIT",
            memory_window_id=None,
        )
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])
        self.assertIsNone(payload["memory_window_id"])

    def test_window_not_closed_backing_fails(self) -> None:
        self._insert_memory_window(window_id=23, window_status="WINDOW_OPEN")
        self._insert_paper_decision(decision_id=1, decision_action="WAIT", memory_window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])

    def test_nonexistent_window_id_backing_fails(self) -> None:
        # Insert with FK disabled so the decision can reference a window that doesn't exist
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = OFF")
            conn.execute(
                "INSERT INTO printer_paper_decisions"
                " (id, token_id, pair_id, decision_action, decision_status,"
                "  memory_window_id, source_status, data_quality_label)"
                " VALUES (1, 10, 10, 'WAIT', 'PAPER_DECISION_PROPOSED',"
                "  9999, 'COMPLETE', 'CLEAN_DATA')"
            )
            conn.commit()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        self.assertFalse(payload["clean_memory_backed"])

    # ------------------------------------------------------------------
    # Decision source/data quality failures
    # ------------------------------------------------------------------

    def test_dirty_data_quality_label_fails(self) -> None:
        self._insert_memory_window(window_id=23)
        self._insert_paper_decision(
            decision_id=1,
            decision_action="WAIT",
            memory_window_id=23,
            data_quality_label="DIRTY_DATA",
        )
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")
        any_reason = any(
            "DIRTY_DATA" in r or "not_clean" in r for r in payload["audit_review_reasons"]
        )
        self.assertTrue(any_reason)

    def test_failed_source_status_fails(self) -> None:
        self._insert_memory_window(window_id=23)
        self._insert_paper_decision(
            decision_id=1,
            decision_action="WAIT",
            memory_window_id=23,
            source_status="FAILED",
        )
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["audit_review_status"], "FAILED")

    # ------------------------------------------------------------------
    # Hard locks — always False
    # ------------------------------------------------------------------

    def test_buy_unlock_always_false_on_pass(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertFalse(payload["buy_unlock"])

    def test_position_unlock_always_false_on_pass(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertFalse(payload["position_unlock"])

    def test_pnl_unlock_always_false_on_pass(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertFalse(payload["pnl_unlock"])

    def test_buy_unlock_always_false_on_fail(self) -> None:
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=9999)
        )
        self.assertFalse(payload["buy_unlock"])

    def test_position_unlock_always_false_on_fail(self) -> None:
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=9999)
        )
        self.assertFalse(payload["position_unlock"])

    def test_pnl_unlock_always_false_on_fail(self) -> None:
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=9999)
        )
        self.assertFalse(payload["pnl_unlock"])

    # ------------------------------------------------------------------
    # Downstream counts — no rows created, zeroes reported
    # ------------------------------------------------------------------

    def test_paper_position_count_for_decision_is_0_when_none(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["paper_position_count_for_decision"], 0)

    def test_paper_trade_event_count_for_decision_is_0_when_none(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["paper_trade_event_count_for_decision"], 0)

    def test_paper_trade_audit_count_for_decision_is_0_when_none(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["paper_trade_audit_count_for_decision"], 0)

    def test_paper_position_delta_always_0(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["paper_position_delta"], 0)

    def test_paper_trade_event_delta_always_0(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["paper_trade_event_delta"], 0)

    def test_paper_trade_audit_delta_always_0(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["paper_trade_audit_delta"], 0)

    # ------------------------------------------------------------------
    # No DB rows written — report-only
    # ------------------------------------------------------------------

    def test_no_paper_position_rows_created(self) -> None:
        self._seed_clean_decision()
        before = self._count_paper_positions()
        build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(self._count_paper_positions(), before)

    def test_no_paper_trade_event_rows_created(self) -> None:
        self._seed_clean_decision()
        before = self._count_paper_trade_events()
        build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(self._count_paper_trade_events(), before)

    def test_no_paper_trade_audit_rows_created(self) -> None:
        self._seed_clean_decision()
        before = self._count_paper_trade_audits()
        build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(self._count_paper_trade_audits(), before)

    def test_no_extra_paper_decision_rows_created(self) -> None:
        self._seed_clean_decision()
        before = self._count_paper_decisions()
        build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(self._count_paper_decisions(), before)

    # ------------------------------------------------------------------
    # Guard integrity — report-only, no writes
    # ------------------------------------------------------------------

    def test_guard_tables_unchanged_on_pass(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["guard_table_deltas"], {})

    def test_guard_tables_unchanged_on_fail(self) -> None:
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=9999)
        )
        self.assertTrue(payload["guard_tables_unchanged"])
        self.assertEqual(payload["guard_table_deltas"], {})

    # ------------------------------------------------------------------
    # Report-only metadata
    # ------------------------------------------------------------------

    def test_report_only_is_true(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertTrue(payload["report_only"])

    def test_review_rows_created_is_0(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["review_rows_created"], 0)

    # ------------------------------------------------------------------
    # Command metadata
    # ------------------------------------------------------------------

    def test_command_name_correct(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(
            payload["command"], "printer-review-conservative-paper-decision-once"
        )

    def test_lane_label_correct(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["lane"], "post_rc_lane8c")
        self.assertEqual(payload["lane_label"], "CONSERVATIVE_PAPER_DECISION_AUDIT_REVIEW")

    def test_operator_approved_is_true(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertTrue(payload["operator_approved"])

    def test_chain_is_solana(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["chain"], "solana")

    def test_paper_decision_id_echoed(self) -> None:
        self._seed_clean_decision(decision_id=42, window_id=42)
        payload = build_conservative_paper_decision_audit_review_payload(
            self.args(paper_decision_id=42)
        )
        self.assertEqual(payload["paper_decision_id"], 42)

    # ------------------------------------------------------------------
    # Blocked actions
    # ------------------------------------------------------------------

    def test_blocked_actions_includes_buy_sell_hold(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        blocked = payload["blocked_actions"]
        self.assertIn("BUY", blocked)
        self.assertIn("SELL", blocked)
        self.assertIn("HOLD", blocked)

    # ------------------------------------------------------------------
    # Memory window echoed
    # ------------------------------------------------------------------

    def test_memory_window_id_echoed(self) -> None:
        self._seed_clean_decision(window_id=23)
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertEqual(payload["memory_window_id"], 23)

    # ------------------------------------------------------------------
    # DB not found
    # ------------------------------------------------------------------

    def test_db_not_found_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            build_conservative_paper_decision_audit_review_payload(
                self.args(db_path="/nonexistent/lane8c.sqlite3")
            )

    # ------------------------------------------------------------------
    # No forbidden fields
    # ------------------------------------------------------------------

    def test_no_scoring_or_confidence_in_payload(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        forbidden = {"score", "confidence", "rank", "weight", "embedding", "vector"}
        for key in payload:
            self.assertNotIn(key.lower(), forbidden, f"Forbidden field found: {key}")

    def test_no_buy_in_accepted_decision_field(self) -> None:
        self._seed_clean_decision()
        payload = build_conservative_paper_decision_audit_review_payload(self.args())
        self.assertNotEqual(payload.get("decision_action"), "BUY")


if __name__ == "__main__":
    unittest.main()
