"""
Post-RC Lane 8B — Conservative Paper Decision Creation

Tests prove:
- command requires --operator-approved
- command requires chain=solana
- BUY is rejected with no writes (paper_decision_delta 0)
- SELL is rejected with no writes
- HOLD is rejected with no writes
- WAIT is accepted and creates exactly one paper decision row
- AVOID is accepted and creates exactly one paper decision row
- NO_ACTION is accepted and creates exactly one paper decision row
- paper_decision_id is returned on creation
- accepted_decision field is present on success
- rejected_decision field is present on rejection
- paper_decision_delta is 1 when a decision is created
- paper_position_delta is always 0
- paper_trade_event_delta is always 0
- paper_trade_audit_delta is always 0
- buy_unlock is False in all paths
- position_unlock is False in all paths
- pnl_unlock is False in all paths
- blocked_actions contains BUY, SELL, HOLD
- guard_tables_unchanged_except_paper_decisions is True when only paper_decisions changed
- memory_window_retrieval_eligible is True on success
- eligible_clean_memory_window_ids contains the window on success
- token_id not found → rejection, no writes
- pair_id not found or wrong token → rejection, no writes
- memory_window_id not found → rejection, no writes
- window token_id mismatch → rejection, no writes
- window pair_id mismatch → rejection, no writes
- window_kind mismatch → rejection, no writes
- WINDOW_5M_MICRO_EVENT is excluded
- AUDIT_ONLY (memory_status) is excluded
- AUDIT_ONLY_MEMORY (memory_quality_label) is excluded
- do_not_train=1 is excluded
- MISSING_CRITICAL_DATA is excluded
- dirty memory (not CLEAN_MEMORY) is excluded
- WINDOW_NOT_CLOSED is excluded
- command name and lane label are correct
- pyproject.toml registers the entry point
- help text works without crashing
- main entry point exits 0
- main entry point prints JSON to stdout
- no scoring/ranking/confidence/weighted logic introduced
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
    build_conservative_paper_decision_payload,
    main_create_conservative_paper_decision_once,
)


def count_rows(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


class Lane8BConservativePaperDecisionTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "lane8b.sqlite3"
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
            "decision": "WAIT",
            "token_id": 10,
            "pair_id": 10,
            "memory_window_id": 23,
            "window_kind": "WINDOW_15M",
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
                " VALUES (10, 'test-mint-lane8b', 'solana', 'L8T', 'Lane8BToken')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex)"
                " VALUES (10, 10, 'test-pair-lane8b', 'raydium')"
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

    def _seed_clean_window(self, window_id: int = 23, window_kind: str = "WINDOW_15M") -> None:
        self._insert_memory_window(window_id=window_id, window_kind=window_kind)

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
        self._seed_clean_window()
        with self.assertRaises(ValueError) as ctx:
            build_conservative_paper_decision_payload(
                self.args(operator_approved=False)
            )
        self.assertIn("operator approval", str(ctx.exception).lower())

    def test_requires_solana_chain(self) -> None:
        self._seed_clean_window()
        with self.assertRaises(ValueError):
            build_conservative_paper_decision_payload(self.args(chain="ethereum"))

    # ------------------------------------------------------------------
    # Help text and entry point
    # ------------------------------------------------------------------

    def test_help_text_works(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            main_create_conservative_paper_decision_once(["--help"])
        self.assertEqual(ctx.exception.code, 0)

    def test_main_entry_point_exits_0_on_wait(self) -> None:
        self._seed_clean_window()
        result = main_create_conservative_paper_decision_once(
            [
                "--operator-approved",
                "--decision", "WAIT",
                "--token-id", "10",
                "--pair-id", "10",
                "--memory-window-id", "23",
                "--window-kind", "WINDOW_15M",
                "--db-path", str(self.db_path),
                "--project-root", str(PROJECT_ROOT),
            ]
        )
        self.assertEqual(result, 0)

    def test_main_entry_point_prints_json_to_stdout(self) -> None:
        self._seed_clean_window()
        buf = io.StringIO()
        with patch("sys.stdout", buf):
            main_create_conservative_paper_decision_once(
                [
                    "--operator-approved",
                    "--decision", "WAIT",
                    "--token-id", "10",
                    "--pair-id", "10",
                    "--memory-window-id", "23",
                    "--window-kind", "WINDOW_15M",
                    "--db-path", str(self.db_path),
                    "--project-root", str(PROJECT_ROOT),
                ]
            )
        output = buf.getvalue()
        self.assertTrue(len(output) > 0)
        parsed = json.loads(output)
        self.assertIn("paper_decision_created", parsed)

    def test_pyproject_registers_entry_point(self) -> None:
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text()
        self.assertIn("printer-create-conservative-paper-decision-once", content)
        self.assertIn("main_create_conservative_paper_decision_once", content)

    # ------------------------------------------------------------------
    # BUY / SELL / HOLD — hard rejection, no writes
    # ------------------------------------------------------------------

    def test_buy_rejected_no_writes(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="BUY")
        )
        after = self._count_paper_decisions()
        self.assertEqual(after, before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertEqual(payload["requested_decision"], "BUY")
        self.assertIn("rejected_decision", payload)
        self.assertEqual(payload["rejected_decision"], "BUY")
        self.assertEqual(payload["paper_decision_delta"], 0)
        self.assertFalse(payload["buy_unlock"])
        self.assertFalse(payload["pnl_unlock"])

    def test_sell_rejected_no_writes(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="SELL")
        )
        after = self._count_paper_decisions()
        self.assertEqual(after, before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertEqual(payload["rejected_decision"], "SELL")
        self.assertEqual(payload["paper_decision_delta"], 0)

    def test_hold_rejected_no_writes(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="HOLD")
        )
        after = self._count_paper_decisions()
        self.assertEqual(after, before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertEqual(payload["rejected_decision"], "HOLD")
        self.assertEqual(payload["paper_decision_delta"], 0)

    def test_buy_rejection_reason_mentions_conservative_only(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="BUY"))
        reason = payload.get("rejection_reason", "")
        self.assertIn("CONSERVATIVE_ONLY", reason)

    # ------------------------------------------------------------------
    # WAIT — accepted, creates one row
    # ------------------------------------------------------------------

    def test_wait_creates_one_paper_decision(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        after = self._count_paper_decisions()
        self.assertEqual(after, before + 1)
        self.assertTrue(payload["paper_decision_created"])
        self.assertEqual(payload["accepted_decision"], "WAIT")
        self.assertNotIn("rejected_decision", payload)

    def test_wait_returns_paper_decision_id(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertIsNotNone(payload["paper_decision_id"])
        self.assertIsInstance(payload["paper_decision_id"], int)
        self.assertGreater(payload["paper_decision_id"], 0)

    def test_wait_paper_decision_delta_is_1(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(payload["paper_decision_delta"], 1)

    # ------------------------------------------------------------------
    # AVOID — accepted
    # ------------------------------------------------------------------

    def test_avoid_creates_one_paper_decision(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="AVOID"))
        after = self._count_paper_decisions()
        self.assertEqual(after, before + 1)
        self.assertTrue(payload["paper_decision_created"])
        self.assertEqual(payload["accepted_decision"], "AVOID")

    def test_avoid_paper_decision_delta_is_1(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="AVOID"))
        self.assertEqual(payload["paper_decision_delta"], 1)

    # ------------------------------------------------------------------
    # NO_ACTION — accepted
    # ------------------------------------------------------------------

    def test_no_action_creates_one_paper_decision(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="NO_ACTION")
        )
        after = self._count_paper_decisions()
        self.assertEqual(after, before + 1)
        self.assertTrue(payload["paper_decision_created"])
        self.assertEqual(payload["accepted_decision"], "NO_ACTION")

    def test_no_action_paper_decision_delta_is_1(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="NO_ACTION")
        )
        self.assertEqual(payload["paper_decision_delta"], 1)

    # ------------------------------------------------------------------
    # Hard locks — always False
    # ------------------------------------------------------------------

    def test_buy_unlock_false_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertFalse(payload["buy_unlock"])

    def test_position_unlock_false_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertFalse(payload["position_unlock"])

    def test_pnl_unlock_false_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertFalse(payload["pnl_unlock"])

    def test_buy_unlock_false_on_rejection(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="BUY"))
        self.assertFalse(payload["buy_unlock"])

    def test_position_unlock_false_on_rejection(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="BUY"))
        self.assertFalse(payload["position_unlock"])

    # ------------------------------------------------------------------
    # Downstream gate deltas — positions/trades/audits always 0
    # ------------------------------------------------------------------

    def test_paper_position_delta_always_0_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(payload["paper_position_delta"], 0)

    def test_paper_trade_event_delta_always_0_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(payload["paper_trade_event_delta"], 0)

    def test_paper_trade_audit_delta_always_0_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(payload["paper_trade_audit_delta"], 0)

    def test_no_paper_position_rows_created(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_positions()
        build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_positions(), before)

    def test_no_paper_trade_event_rows_created(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_trade_events()
        build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_trade_events(), before)

    def test_no_paper_trade_audit_rows_created(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_trade_audits()
        build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_trade_audits(), before)

    # ------------------------------------------------------------------
    # Guard integrity
    # ------------------------------------------------------------------

    def test_guard_tables_unchanged_except_paper_decisions_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertTrue(payload["guard_tables_unchanged_except_paper_decisions"])

    def test_guard_table_deltas_shows_only_paper_decisions_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        deltas = payload["guard_table_deltas"]
        self.assertEqual(list(deltas.keys()), ["printer_paper_decisions"])
        self.assertEqual(deltas["printer_paper_decisions"], 1)

    def test_guard_tables_unchanged_on_buy_rejection(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="BUY"))
        self.assertTrue(payload["guard_tables_unchanged_except_paper_decisions"])
        self.assertEqual(payload["guard_table_deltas"], {})

    # ------------------------------------------------------------------
    # Blocked actions
    # ------------------------------------------------------------------

    def test_blocked_actions_includes_buy_sell_hold(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        blocked = payload["blocked_actions"]
        self.assertIn("BUY", blocked)
        self.assertIn("SELL", blocked)
        self.assertIn("HOLD", blocked)

    def test_blocked_actions_present_on_rejection(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="BUY"))
        blocked = payload["blocked_actions"]
        self.assertIn("BUY", blocked)
        self.assertIn("SELL", blocked)
        self.assertIn("HOLD", blocked)

    # ------------------------------------------------------------------
    # Memory retrieval eligibility
    # ------------------------------------------------------------------

    def test_memory_window_retrieval_eligible_true_on_wait(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertTrue(payload["memory_window_retrieval_eligible"])

    def test_eligible_clean_memory_window_ids_contains_window(self) -> None:
        self._seed_clean_window(window_id=23)
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertIn(23, payload["eligible_clean_memory_window_ids"])

    def test_memory_window_retrieval_eligible_false_on_rejection(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="BUY"))
        self.assertFalse(payload["memory_window_retrieval_eligible"])

    # ------------------------------------------------------------------
    # Command metadata
    # ------------------------------------------------------------------

    def test_command_name_correct(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(
            payload["command"], "printer-create-conservative-paper-decision-once"
        )

    def test_lane_label_correct(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(payload["lane"], "post_rc_lane8b")
        self.assertEqual(payload["lane_label"], "CONSERVATIVE_PAPER_DECISION_CREATION")

    def test_report_only_is_false(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertFalse(payload["report_only"])

    def test_operator_approved_is_true(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertTrue(payload["operator_approved"])

    def test_chain_is_solana(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(payload["chain"], "solana")

    # ------------------------------------------------------------------
    # Entity verification — token not found
    # ------------------------------------------------------------------

    def test_unknown_token_id_rejected_no_writes(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="WAIT", token_id=999)
        )
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("999", payload.get("rejection_reason", ""))

    # ------------------------------------------------------------------
    # Entity verification — pair not found / wrong token
    # ------------------------------------------------------------------

    def test_unknown_pair_id_rejected_no_writes(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="WAIT", pair_id=999)
        )
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])

    # ------------------------------------------------------------------
    # Entity verification — memory window not found
    # ------------------------------------------------------------------

    def test_unknown_memory_window_id_rejected_no_writes(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="WAIT", memory_window_id=9999)
        )
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("9999", payload.get("rejection_reason", ""))

    # ------------------------------------------------------------------
    # Entity verification — window belongs to wrong token
    # ------------------------------------------------------------------

    def test_window_wrong_token_rejected(self) -> None:
        # Insert a second token and pair, then insert window under original token
        # but claim it belongs to the new token via args
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO printer_tokens (id, token_mint, chain, symbol, name)"
                " VALUES (20, 'other-mint', 'solana', 'OTH', 'OtherToken')"
            )
            conn.execute(
                "INSERT INTO printer_pairs (id, token_id, pair_address, dex)"
                " VALUES (20, 20, 'other-pair', 'raydium')"
            )
        self._seed_clean_window(window_id=23)  # window is under token_id=10, pair_id=10
        payload = build_conservative_paper_decision_payload(
            self.args(decision="WAIT", token_id=20, pair_id=20)
        )
        self.assertFalse(payload["paper_decision_created"])

    # ------------------------------------------------------------------
    # Entity verification — window_kind mismatch
    # ------------------------------------------------------------------

    def test_window_kind_mismatch_rejected(self) -> None:
        self._seed_clean_window(window_id=23, window_kind="WINDOW_15M")
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="WAIT", window_kind="WINDOW_1H")
        )
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("mismatch", payload.get("rejection_reason", "").lower())

    # ------------------------------------------------------------------
    # Lane 7 eligibility exclusions
    # ------------------------------------------------------------------

    def test_window_5m_micro_event_excluded(self) -> None:
        self._insert_memory_window(window_id=23, window_kind="WINDOW_5M_MICRO_EVENT")
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(
            self.args(decision="WAIT", window_kind="WINDOW_5M_MICRO_EVENT")
        )
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("5M_MICRO_EVENT", payload.get("rejection_reason", ""))

    def test_audit_only_memory_status_excluded(self) -> None:
        self._insert_memory_window(
            window_id=23, memory_status="AUDIT_ONLY", memory_quality_label="CLEAN_MEMORY"
        )
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("AUDIT_ONLY", payload.get("rejection_reason", ""))

    def test_audit_only_memory_quality_label_excluded(self) -> None:
        self._insert_memory_window(
            window_id=23,
            memory_status="CLEAN_MEMORY",
            memory_quality_label="AUDIT_ONLY_MEMORY",
        )
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("AUDIT_ONLY", payload.get("rejection_reason", ""))

    def test_do_not_train_excluded(self) -> None:
        self._insert_memory_window(window_id=23, do_not_train=1)
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("do_not_train", payload.get("rejection_reason", ""))

    def test_missing_critical_data_excluded(self) -> None:
        self._insert_memory_window(
            window_id=23, data_quality_label="MISSING_CRITICAL_DATA"
        )
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("MISSING_CRITICAL_DATA", payload.get("rejection_reason", ""))

    def test_dirty_memory_status_excluded(self) -> None:
        self._insert_memory_window(
            window_id=23,
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
        )
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("NOT_CLEAN_MEMORY", payload.get("rejection_reason", ""))

    def test_dirty_data_quality_excluded(self) -> None:
        self._insert_memory_window(window_id=23, data_quality_label="DIRTY_DATA")
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("NOT_CLEAN_DATA", payload.get("rejection_reason", ""))

    def test_window_not_closed_excluded(self) -> None:
        self._insert_memory_window(window_id=23, window_status="WINDOW_OPEN")
        before = self._count_paper_decisions()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before)
        self.assertFalse(payload["paper_decision_created"])
        self.assertIn("WINDOW_NOT_CLOSED", payload.get("rejection_reason", ""))

    # ------------------------------------------------------------------
    # DB row content verification
    # ------------------------------------------------------------------

    def test_created_row_has_correct_decision_action(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="AVOID"))
        decision_id = payload["paper_decision_id"]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM printer_paper_decisions WHERE id = ?", (decision_id,)
            ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["decision_action"], "AVOID")

    def test_created_row_has_proposed_status(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        decision_id = payload["paper_decision_id"]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT decision_status FROM printer_paper_decisions WHERE id = ?",
                (decision_id,),
            ).fetchone()
        self.assertEqual(row["decision_status"], "PAPER_DECISION_PROPOSED")

    def test_created_row_links_memory_window(self) -> None:
        self._seed_clean_window(window_id=23)
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        decision_id = payload["paper_decision_id"]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT memory_window_id FROM printer_paper_decisions WHERE id = ?",
                (decision_id,),
            ).fetchone()
        self.assertEqual(row["memory_window_id"], 23)

    def test_created_row_clean_data_label(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        decision_id = payload["paper_decision_id"]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT data_quality_label FROM printer_paper_decisions WHERE id = ?",
                (decision_id,),
            ).fetchone()
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")

    def test_created_row_gate_label_decision_allowed(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        decision_id = payload["paper_decision_id"]
        with self._connect() as conn:
            row = conn.execute(
                "SELECT decision_gate_label FROM printer_paper_decisions WHERE id = ?",
                (decision_id,),
            ).fetchone()
        self.assertEqual(row["decision_gate_label"], "DECISION_ALLOWED")

    # ------------------------------------------------------------------
    # Exactly one row created (not multiple)
    # ------------------------------------------------------------------

    def test_exactly_one_row_created_per_call(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        self.assertEqual(self._count_paper_decisions(), before + 1)

    def test_two_calls_create_two_rows(self) -> None:
        self._seed_clean_window()
        before = self._count_paper_decisions()
        build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        build_conservative_paper_decision_payload(self.args(decision="AVOID"))
        self.assertEqual(self._count_paper_decisions(), before + 2)

    # ------------------------------------------------------------------
    # DB not found
    # ------------------------------------------------------------------

    def test_db_not_found_raises(self) -> None:
        with self.assertRaises(FileNotFoundError):
            build_conservative_paper_decision_payload(
                self.args(db_path="/nonexistent/path/lane8b.sqlite3")
            )

    # ------------------------------------------------------------------
    # No forbidden fields
    # ------------------------------------------------------------------

    def test_no_scoring_or_confidence_in_payload(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        forbidden = {
            "score", "confidence", "rank", "weight", "embedding", "vector"
        }
        for key in payload:
            self.assertNotIn(key.lower(), forbidden, f"Forbidden field found: {key}")

    def test_no_buy_in_accepted_decision(self) -> None:
        self._seed_clean_window()
        payload = build_conservative_paper_decision_payload(self.args(decision="WAIT"))
        accepted = payload.get("accepted_decision", "")
        self.assertNotEqual(accepted, "BUY")


if __name__ == "__main__":
    unittest.main()
