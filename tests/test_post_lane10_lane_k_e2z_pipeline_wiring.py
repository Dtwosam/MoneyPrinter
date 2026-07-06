"""
Post-Lane 10 Lane K -- E2Q-to-E2Z Clean-Memory Pipeline Wiring Boundary

Twelve boundary proofs:
 1.  Approval required — LANE_K_BLOCKED without operator_approved
 2.  DB path required — LANE_K_BLOCKED without db_path or with bad path
 3.  Zero-clean outcome is valid — LANE_K_COMPLETED when E2Y gate not passed
 4.  Full E2X → E2Y → E2Z flow creates correct number of CLEAN_MEMORY episodes
 5.  Idempotency — rerun creates no duplicate episodes
 6.  Dirty / audit-only / 5m / do_not_train evidence is blocked (not eligible)
 7.  No retrieval activated
 8.  No paper decisions / BUY / SELL / HOLD
 9.  No positions / trade events / audits / PnL
10.  No source requests / responses / failures created
11.  No scheduler jobs created
12.  Hard locks stay True; locked capabilities stay False
"""

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import (
    LANE_K_STATUS_BLOCKED,
    LANE_K_STATUS_COMPLETED,
    _HARD_LOCKS,
    _LOCKED_CAPABILITIES,
    run_e2z_pipeline,
)


_MINT = "LaneKTestMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR = "LaneKTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_NOW = "2026-06-29T10:00:00+00:00"

# Default real 15m window boundaries (>= 900 s elapsed) for Lane Q guard
_WIN_START = "2026-06-29T10:00:00+00:00"
_WIN_END = "2026-06-29T10:15:01+00:00"  # 901 seconds later

_CLEAN_CTX_TMPL = json.dumps({
    "snapshot_id": 0,
    "e2q_audited": True,
    "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
    "e2q_audited_by": "lane_e2q",
}, sort_keys=True)


def _clean_ctx(snapshot_id: int) -> str:
    return json.dumps({
        "snapshot_id": snapshot_id,
        "e2q_audited": True,
        "e2q_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
        "e2q_audited_by": "lane_e2q",
    }, sort_keys=True)


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _connect(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _count(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            r = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return r[0] if r else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _insert_token(self, conn) -> int:
        cur = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACKING', ?, ?)",
            (_MINT, _NOW, _NOW, _NOW, _NOW),
        )
        return int(cur.lastrowid)

    def _insert_pair(self, conn, token_id: int) -> int:
        cur = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, _PAIR, _PAIR, _NOW, _NOW, _NOW, _NOW),
        )
        return int(cur.lastrowid)

    def _insert_window(
        self,
        conn,
        token_id: int,
        pair_id: int,
        *,
        window_kind: str = "WINDOW_15M",
        window_status: str = "WINDOW_CLOSED",
        memory_status: str = "PARTIAL_MEMORY",
        memory_quality_label: str = "PARTIAL_MEMORY",
        data_quality_label: str = "CLEAN_DATA",
        do_not_train: int = 0,
        supporting_context_json: str | None = None,
        snapshot_id: int = 99,
        window_start_at: str | None = _WIN_START,
        window_end_at: str | None = _WIN_END,
        snapshot_start_id: int | None = 1,
        snapshot_end_id: int | None = 2,
    ) -> int:
        if supporting_context_json is None:
            supporting_context_json = _clean_ctx(snapshot_id)
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, window_kind, _NOW, _NOW,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, _NOW, _NOW,
                window_start_at, window_end_at,
                snapshot_start_id, snapshot_end_id,
            ),
        )
        return int(cur.lastrowid)

    def _make_five_eligible(self) -> tuple[int, int, list[int]]:
        """Insert 5 eligible WINDOW_15M rows for the same token/pair."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wids = []
            for snapshot_id in (101, 102, 103, 104, 105):
                wid = self._insert_window(
                    conn, tid, pid, snapshot_id=snapshot_id
                )
                wids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return tid, pid, wids

    def _run(self, *, operator_approved: bool = True) -> dict:
        return run_e2z_pipeline(self.db_path, operator_approved=operator_approved)


# ===========================================================================
# Proof 1 — Approval required
# ===========================================================================

class LaneKApprovalTests(_Base):
    def test_blocked_without_approval(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_BLOCKED)

    def test_blocked_has_reasons(self):
        r = self._run(operator_approved=False)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_blocked_approval_reason_text(self):
        r = self._run(operator_approved=False)
        self.assertTrue(any("operator_approved" in s for s in r["blocked_reasons"]))

    def test_blocked_zero_clean_memories(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_blocked_e2z_counts_are_zero(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["e2z_created_count"], 0)
        self.assertEqual(r["e2z_already_exists_count"], 0)
        self.assertEqual(r["e2z_blocked_count"], 0)

    def test_zero_clean_memories_valid_on_blocked(self):
        r = self._run(operator_approved=False)
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_no_episodes_created_on_blocked(self):
        before = self._count("printer_episodes")
        self._run(operator_approved=False)
        self.assertEqual(self._count("printer_episodes"), before)

    def test_hard_locks_present_on_blocked(self):
        r = self._run(operator_approved=False)
        self.assertIn("hard_locks", r)
        self.assertTrue(all(r["hard_locks"].values()))

    def test_locked_capabilities_present_on_blocked(self):
        r = self._run(operator_approved=False)
        self.assertIn("locked_capabilities", r)
        self.assertFalse(any(r["locked_capabilities"].values()))


# ===========================================================================
# Proof 2 — DB path required
# ===========================================================================

class LaneKDbPathTests(unittest.TestCase):
    def test_blocked_without_db_path(self):
        r = run_e2z_pipeline(None, operator_approved=True)
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_BLOCKED)

    def test_blocked_reason_on_none_db(self):
        r = run_e2z_pipeline(None, operator_approved=True)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_blocked_with_nonexistent_path(self):
        r = run_e2z_pipeline("/nonexistent/path/db.sqlite3", operator_approved=True)
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_BLOCKED)

    def test_blocked_reason_on_missing_file(self):
        r = run_e2z_pipeline("/nonexistent/path/db.sqlite3", operator_approved=True)
        self.assertTrue(any("db_path" in s or "not found" in s for s in r["blocked_reasons"]))

    def test_zero_clean_on_missing_db(self):
        r = run_e2z_pipeline(None, operator_approved=True)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_zero_clean_memories_valid_on_bad_db(self):
        r = run_e2z_pipeline(None, operator_approved=True)
        self.assertIs(r["zero_clean_memories_valid"], True)


# ===========================================================================
# Proof 3 — Zero-clean outcome is valid (E2Y gate not passed)
# ===========================================================================

class LaneKZeroCleanTests(_Base):
    def test_completed_on_empty_db(self):
        r = self._run()
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_zero_clean_on_empty_db(self):
        r = self._run()
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_zero_clean_memories_valid_always(self):
        r = self._run()
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_e2y_set_gate_false_on_empty_db(self):
        r = self._run()
        self.assertIs(r["e2y_set_gate_passed"], False)

    def test_candidate_window_ids_empty_on_zero_clean(self):
        r = self._run()
        self.assertEqual(r["candidate_window_ids"], [])

    def test_no_episodes_created_on_zero_clean(self):
        before = self._count("printer_episodes")
        self._run()
        self.assertEqual(self._count("printer_episodes"), before)

    def test_e2z_counts_all_zero_on_zero_clean(self):
        r = self._run()
        self.assertEqual(r["e2z_created_count"], 0)
        self.assertEqual(r["e2z_already_exists_count"], 0)
        self.assertEqual(r["e2z_blocked_count"], 0)

    def test_lane_k_completed_not_error_on_zero_clean(self):
        r = self._run()
        self.assertNotEqual(r["lane_k_status"], LANE_K_STATUS_BLOCKED)

    def test_one_individually_eligible_window_is_promoted(self):
        """Single eligible window — E2Y batch gate fails (count < 5) but
        individual promotion still creates 1 clean memory row."""
        conn = self._connect()
        try:
            tid = conn.execute(
                "INSERT INTO printer_tokens"
                " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
                "  token_status, created_at, updated_at)"
                " VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACKING', ?, ?)",
                (_MINT, _NOW, _NOW, _NOW, _NOW),
            ).lastrowid
            pid = conn.execute(
                "INSERT INTO printer_pairs"
                " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
                "  created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (tid, _PAIR, _PAIR, _NOW, _NOW, _NOW, _NOW),
            ).lastrowid
            # 1 individually eligible window — E2Y batch gate fails (count < 5)
            # but per-window gate in E2Z passes, so it is promoted.
            self._insert_window(conn, tid, pid, snapshot_id=50)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_COMPLETED)
        # Individual promotion: 1 eligible window → 1 clean memory row.
        self.assertEqual(r["clean_memory_rows_created"], 1)
        self.assertIs(r["zero_clean_memories_valid"], True)
        # E2Y batch gate still reports failure (informational, not gating).
        self.assertIs(r["e2y_set_gate_passed"], False)


# ===========================================================================
# Proof 4 — Full E2X → E2Y → E2Z flow creates clean memory
# ===========================================================================

class LaneKFullFlowTests(_Base):
    def _setup_and_run(self):
        self._make_five_eligible()
        return self._run()

    def test_full_flow_lane_k_completed(self):
        r = self._setup_and_run()
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_full_flow_e2y_set_gate_passed(self):
        r = self._setup_and_run()
        self.assertIs(r["e2y_set_gate_passed"], True)

    def test_full_flow_creates_5_episodes(self):
        before = self._count("printer_episodes")
        r = self._setup_and_run()
        self.assertEqual(r["e2z_created_count"], 5)
        self.assertEqual(self._count("printer_episodes"), before + 5)
        # Lane Q must pass all 5 (valid timestamps and snapshot IDs present)
        self.assertEqual(r.get("lane_q_blocked_count", 0), 0)

    def test_full_flow_clean_memory_rows_created_equals_created_count(self):
        r = self._setup_and_run()
        self.assertEqual(r["clean_memory_rows_created"], r["e2z_created_count"])

    def test_full_flow_candidate_window_ids_is_5(self):
        r = self._setup_and_run()
        self.assertEqual(len(r["candidate_window_ids"]), 5)

    def test_full_flow_zero_already_exists_first_run(self):
        r = self._setup_and_run()
        self.assertEqual(r["e2z_already_exists_count"], 0)

    def test_full_flow_zero_blocked_on_clean_candidates(self):
        r = self._setup_and_run()
        self.assertEqual(r["e2z_blocked_count"], 0)

    def test_full_flow_episodes_are_clean_memory(self):
        _, _, wids = self._make_five_eligible()
        self._run()
        conn = self._connect()
        try:
            for wid in wids:
                row = conn.execute(
                    "SELECT memory_status FROM printer_episodes"
                    " WHERE memory_window_id = ?",
                    (wid,),
                ).fetchone()
                self.assertIsNotNone(row, f"no episode for window {wid}")
                self.assertEqual(row["memory_status"], "CLEAN_MEMORY")
        finally:
            conn.close()

    def test_full_flow_one_episode_per_window(self):
        """Each window gets exactly one CLEAN_MEMORY episode."""
        _, _, wids = self._make_five_eligible()
        self._run()
        conn = self._connect()
        try:
            for wid in wids:
                count = conn.execute(
                    "SELECT COUNT(*) FROM printer_episodes"
                    " WHERE memory_window_id = ? AND memory_status = 'CLEAN_MEMORY'",
                    (wid,),
                ).fetchone()[0]
                self.assertEqual(count, 1, f"expected 1 episode for window {wid}")
        finally:
            conn.close()

    def test_full_flow_db_delta_summary_episodes_delta_is_5(self):
        r = self._setup_and_run()
        delta = r["db_delta_summary"]["printer_episodes"]["delta"]
        self.assertEqual(delta, 5)

    def test_full_flow_e2x_status_ready(self):
        r = self._setup_and_run()
        self.assertEqual(r["e2x_status"], "E2X_REVIEW_READY")

    def test_full_flow_e2y_status_ready(self):
        r = self._setup_and_run()
        self.assertEqual(r["e2y_status"], "E2Y_SET_GATE_READY")


# ===========================================================================
# Proof 5 — Idempotency: rerun creates no duplicates
# ===========================================================================

class LaneKIdempotencyTests(_Base):
    def _setup(self):
        self._make_five_eligible()

    def test_rerun_returns_already_exists(self):
        self._setup()
        self._run()  # first run — creates 5
        r2 = self._run()  # second run — should be all already_exists
        self.assertEqual(r2["e2z_already_exists_count"], 5)
        self.assertEqual(r2["e2z_created_count"], 0)

    def test_rerun_no_new_episodes(self):
        self._setup()
        self._run()
        before = self._count("printer_episodes")
        self._run()
        self.assertEqual(self._count("printer_episodes"), before)

    def test_rerun_lane_k_still_completed(self):
        self._setup()
        self._run()
        r2 = self._run()
        self.assertEqual(r2["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_rerun_clean_memory_rows_created_zero(self):
        self._setup()
        self._run()
        r2 = self._run()
        self.assertEqual(r2["clean_memory_rows_created"], 0)

    def test_rerun_zero_clean_still_valid(self):
        self._setup()
        self._run()
        r2 = self._run()
        self.assertIs(r2["zero_clean_memories_valid"], True)

    def test_rerun_db_delta_episodes_is_zero(self):
        self._setup()
        self._run()
        r2 = self._run()
        delta = r2["db_delta_summary"]["printer_episodes"]["delta"]
        self.assertEqual(delta, 0)


# ===========================================================================
# Proof 6 — Dirty / 5m / do_not_train / non-e2q evidence is blocked
# ===========================================================================

class LaneKDirtyBlockedTests(_Base):
    def _insert_token_pair(self, conn):
        tid = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACKING', ?, ?)",
            (_MINT, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid
        pid = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (tid, _PAIR, _PAIR, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid
        return tid, pid

    def _run_with_only(self, **window_kwargs) -> dict:
        conn = self._connect()
        try:
            tid, pid = self._insert_token_pair(conn)
            self._insert_window(conn, tid, pid, **window_kwargs)
            conn.commit()
        finally:
            conn.close()
        return self._run()

    def test_dirty_data_not_eligible(self):
        r = self._run_with_only(data_quality_label="DIRTY_DATA", snapshot_id=1)
        self.assertEqual(r["clean_memory_rows_created"], 0)
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_stale_data_not_eligible(self):
        r = self._run_with_only(data_quality_label="STALE_DATA", snapshot_id=1)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_do_not_train_not_eligible(self):
        r = self._run_with_only(do_not_train=1, snapshot_id=1)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_5m_window_not_eligible(self):
        r = self._run_with_only(window_kind="WINDOW_5M_MICRO_EVENT", snapshot_id=1)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_window_not_closed_not_eligible(self):
        r = self._run_with_only(window_status="WINDOW_OPEN", snapshot_id=1)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_non_partial_memory_not_eligible(self):
        r = self._run_with_only(memory_status="DIRTY_MEMORY", snapshot_id=1)
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_no_e2q_audit_not_eligible(self):
        no_audit_ctx = json.dumps({
            "snapshot_id": 10,
            "e2q_audited": False,
        }, sort_keys=True)
        r = self._run_with_only(
            supporting_context_json=no_audit_ctx, snapshot_id=10
        )
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_no_snapshot_link_not_eligible(self):
        no_link_ctx = json.dumps({
            "e2q_audited": True,
            "e2q_audited_by": "lane_e2q",
        }, sort_keys=True)
        r = self._run_with_only(
            supporting_context_json=no_link_ctx, snapshot_id=10
        )
        self.assertEqual(r["clean_memory_rows_created"], 0)

    def test_dirty_windows_produce_zero_clean_which_is_valid(self):
        r = self._run_with_only(data_quality_label="DIRTY_DATA", snapshot_id=1)
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_no_episodes_created_from_dirty(self):
        before = self._count("printer_episodes")
        self._run_with_only(data_quality_label="DIRTY_DATA", snapshot_id=1)
        self.assertEqual(self._count("printer_episodes"), before)


# ===========================================================================
# Proof 7 — No retrieval activated
# ===========================================================================

class LaneKNoRetrievalTests(_Base):
    def test_retrieval_activated_false_on_blocked(self):
        r = self._run(operator_approved=False)
        self.assertIs(r["retrieval_activated"], False)

    def test_retrieval_activated_false_on_zero_clean(self):
        r = self._run()
        self.assertIs(r["retrieval_activated"], False)

    def test_retrieval_activated_false_after_full_flow(self):
        self._make_five_eligible()
        r = self._run()
        self.assertIs(r["retrieval_activated"], False)

    def test_hard_lock_no_retrieval_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_retrieval_activation"], True)

    def test_locked_capability_retrieval_false(self):
        r = self._run()
        self.assertIs(r["locked_capabilities"]["retrieval_active"], False)

    def test_retrieval_tables_unchanged(self):
        before = self._count("printer_memory_retrieval_queries")
        self._make_five_eligible()
        self._run()
        self.assertEqual(self._count("printer_memory_retrieval_queries"), before)


# ===========================================================================
# Proof 8 — No paper decisions / BUY / SELL / HOLD
# ===========================================================================

class LaneKNoPaperDecisionTests(_Base):
    def test_paper_decisions_created_zero_blocked(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_paper_decisions_created_zero_zero_clean(self):
        r = self._run()
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_paper_decisions_created_zero_full_flow(self):
        self._make_five_eligible()
        r = self._run()
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_buy_enabled_false(self):
        self._make_five_eligible()
        r = self._run()
        self.assertIs(r["buy_enabled"], False)

    def test_sell_enabled_false(self):
        self._make_five_eligible()
        r = self._run()
        self.assertIs(r["sell_enabled"], False)

    def test_hold_enabled_false(self):
        self._make_five_eligible()
        r = self._run()
        self.assertIs(r["hold_enabled"], False)

    def test_hard_lock_no_paper_decisions_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_paper_decisions"], True)

    def test_hard_lock_no_buy_sell_hold_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_buy_sell_hold"], True)

    def test_paper_decisions_table_unchanged(self):
        before = self._count("printer_paper_decisions")
        self._make_five_eligible()
        self._run()
        self.assertEqual(self._count("printer_paper_decisions"), before)

    def test_locked_capability_buy_false(self):
        r = self._run()
        self.assertIs(r["locked_capabilities"]["buy_unlock_active"], False)

    def test_locked_capability_paper_decision_false(self):
        r = self._run()
        self.assertIs(r["locked_capabilities"]["paper_decision_creation_active"], False)


# ===========================================================================
# Proof 9 — No positions / trade events / audits / PnL
# ===========================================================================

class LaneKNoPositionsTests(_Base):
    def test_positions_created_zero(self):
        self._make_five_eligible()
        r = self._run()
        self.assertEqual(r["positions_created"], 0)

    def test_pnl_created_zero(self):
        self._make_five_eligible()
        r = self._run()
        self.assertEqual(r["pnl_created"], 0)

    def test_trade_events_created_zero(self):
        self._make_five_eligible()
        r = self._run()
        self.assertEqual(r["trade_events_created"], 0)

    def test_paper_trade_audits_created_zero(self):
        self._make_five_eligible()
        r = self._run()
        self.assertEqual(r["paper_trade_audits_created"], 0)

    def test_hard_lock_no_positions_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_positions"], True)

    def test_hard_lock_no_pnl_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_pnl"], True)

    def test_hard_lock_no_trade_events_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_trade_events_created"], True)

    def test_hard_lock_no_paper_trade_audits_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_paper_trade_audits_created"], True)

    def test_paper_positions_table_unchanged(self):
        before = self._count("printer_paper_positions")
        self._make_five_eligible()
        self._run()
        self.assertEqual(self._count("printer_paper_positions"), before)

    def test_paper_trade_events_table_unchanged(self):
        before = self._count("printer_paper_trade_events")
        self._make_five_eligible()
        self._run()
        self.assertEqual(self._count("printer_paper_trade_events"), before)

    def test_paper_trade_audits_table_unchanged(self):
        before = self._count("printer_paper_trade_audits")
        self._make_five_eligible()
        self._run()
        self.assertEqual(self._count("printer_paper_trade_audits"), before)

    def test_locked_capability_pnl_false(self):
        r = self._run()
        self.assertIs(r["locked_capabilities"]["pnl_active"], False)

    def test_locked_capability_trade_events_false(self):
        r = self._run()
        self.assertIs(r["locked_capabilities"]["trade_events_active"], False)


# ===========================================================================
# Proof 10 — No source requests / responses / failures created
# ===========================================================================

class LaneKNoSourceTests(_Base):
    def test_no_source_requests_on_zero_clean(self):
        before = self._count("printer_source_requests")
        self._run()
        self.assertEqual(self._count("printer_source_requests"), before)

    def test_no_source_requests_after_full_flow(self):
        self._make_five_eligible()
        before = self._count("printer_source_requests")
        self._run()
        self.assertEqual(self._count("printer_source_requests"), before)

    def test_no_source_responses_after_full_flow(self):
        self._make_five_eligible()
        before = self._count("printer_source_responses")
        self._run()
        self.assertEqual(self._count("printer_source_responses"), before)

    def test_no_source_failures_after_full_flow(self):
        self._make_five_eligible()
        before = self._count("printer_source_failures")
        self._run()
        self.assertEqual(self._count("printer_source_failures"), before)

    def test_hard_lock_no_source_fetching_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_source_fetching"], True)

    def test_hard_lock_no_source_requests_created_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_source_requests_created"], True)

    def test_db_delta_source_requests_delta_zero(self):
        self._make_five_eligible()
        r = self._run()
        delta = r["db_delta_summary"]["printer_source_requests"]["delta"]
        self.assertEqual(delta, 0)

    def test_db_delta_source_responses_delta_zero(self):
        self._make_five_eligible()
        r = self._run()
        delta = r["db_delta_summary"]["printer_source_responses"]["delta"]
        self.assertEqual(delta, 0)

    def test_locked_capability_source_requests_false(self):
        r = self._run()
        self.assertIs(r["locked_capabilities"]["source_requests_created"], False)


# ===========================================================================
# Proof 11 — No scheduler jobs created
# ===========================================================================

class LaneKNoSchedulerTests(_Base):
    def test_no_scheduler_jobs_on_zero_clean(self):
        before = self._count("printer_scheduler_jobs")
        self._run()
        self.assertEqual(self._count("printer_scheduler_jobs"), before)

    def test_no_scheduler_jobs_after_full_flow(self):
        self._make_five_eligible()
        before = self._count("printer_scheduler_jobs")
        self._run()
        self.assertEqual(self._count("printer_scheduler_jobs"), before)

    def test_hard_lock_no_scheduler_jobs_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_scheduler_jobs_created"], True)

    def test_hard_lock_no_scheduler_runtime_expansion_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_scheduler_runtime_expansion"], True)

    def test_db_delta_scheduler_jobs_delta_zero(self):
        self._make_five_eligible()
        r = self._run()
        delta = r["db_delta_summary"]["printer_scheduler_jobs"]["delta"]
        self.assertEqual(delta, 0)

    def test_locked_capability_scheduler_jobs_false(self):
        r = self._run()
        self.assertIs(r["locked_capabilities"]["scheduler_jobs_created"], False)


# ===========================================================================
# Proof 12 — Hard locks stay True; locked capabilities stay False
# ===========================================================================

class LaneKHardLockTests(_Base):
    def _all_lock_keys(self):
        return set(_HARD_LOCKS.keys())

    def _all_capability_keys(self):
        return set(_LOCKED_CAPABILITIES.keys())

    def test_all_hard_locks_true_on_blocked(self):
        r = self._run(operator_approved=False)
        for key, val in r["hard_locks"].items():
            self.assertIs(val, True, f"hard_lock '{key}' was not True on blocked")

    def test_all_hard_locks_true_on_zero_clean(self):
        r = self._run()
        for key, val in r["hard_locks"].items():
            self.assertIs(val, True, f"hard_lock '{key}' was not True on zero-clean")

    def test_all_hard_locks_true_after_full_flow(self):
        self._make_five_eligible()
        r = self._run()
        for key, val in r["hard_locks"].items():
            self.assertIs(val, True, f"hard_lock '{key}' was not True after full flow")

    def test_all_locked_capabilities_false_on_blocked(self):
        r = self._run(operator_approved=False)
        for key, val in r["locked_capabilities"].items():
            self.assertIs(val, False, f"locked_capability '{key}' was not False on blocked")

    def test_all_locked_capabilities_false_on_zero_clean(self):
        r = self._run()
        for key, val in r["locked_capabilities"].items():
            self.assertIs(val, False, f"locked_capability '{key}' was not False on zero-clean")

    def test_all_locked_capabilities_false_after_full_flow(self):
        self._make_five_eligible()
        r = self._run()
        for key, val in r["locked_capabilities"].items():
            self.assertIs(val, False, f"locked_capability '{key}' was not False after full flow")

    def test_hard_lock_keys_match_expected(self):
        r = self._run()
        self.assertEqual(set(r["hard_locks"].keys()), self._all_lock_keys())

    def test_locked_capability_keys_match_expected(self):
        r = self._run()
        self.assertEqual(set(r["locked_capabilities"].keys()), self._all_capability_keys())

    def test_zero_clean_memories_valid_true_on_blocked(self):
        r = self._run(operator_approved=False)
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_zero_clean_memories_valid_true_on_zero_clean(self):
        r = self._run()
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_zero_clean_memories_valid_true_after_full_flow(self):
        self._make_five_eligible()
        r = self._run()
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_no_new_write_path_outside_e2z_lock_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_new_write_path_outside_e2z"], True)

    def test_no_live_trading_lock_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_live_trading"], True)

    def test_no_wallet_private_key_lock_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_wallet_private_key"], True)

    def test_no_5m_main_outcome_lock_true(self):
        r = self._run()
        self.assertIs(r["hard_locks"]["no_5m_main_outcome"], True)

    def test_recommended_next_action_present(self):
        r = self._run()
        self.assertIn("recommended_next_action", r)
        self.assertIsInstance(r["recommended_next_action"], str)
        self.assertGreater(len(r["recommended_next_action"]), 0)


# ===========================================================================
# Proof 13 — Mixed batch: DIRTY_MEMORY + PARTIAL_MEMORY windows
# Only individually eligible PARTIAL_MEMORY rows must be promoted.
# ===========================================================================

class LaneKMixedBatchTests(_Base):
    """Prove that a mixed batch (clean + dirty) promotes only the clean windows.

    This is the key regression for the real 1h X5 run where 3 PARTIAL_MEMORY
    windows + 10 DIRTY_MEMORY windows caused zero clean memories because the
    E2Y batch gate required ALL candidates to be PARTIAL_MEMORY.
    """

    def _insert_dirty_window(self, conn, token_id: int, pair_id: int, snapshot_id: int = 1) -> int:
        """Insert a DIRTY_MEMORY window that must never become clean."""
        return self._insert_window(
            conn, token_id, pair_id,
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
            data_quality_label="MISSING_CRITICAL_DATA",
            do_not_train=1,
            snapshot_id=snapshot_id,
        )

    def _insert_do_not_train_window(self, conn, token_id: int, pair_id: int, snapshot_id: int = 2) -> int:
        """Insert a window with do_not_train=1 that must never become clean."""
        return self._insert_window(
            conn, token_id, pair_id,
            memory_status="PARTIAL_MEMORY",
            memory_quality_label="PARTIAL_MEMORY",
            data_quality_label="CLEAN_DATA",
            do_not_train=1,
            snapshot_id=snapshot_id,
        )

    def _make_mixed_three_clean_ten_dirty(self):
        """Insert 3 eligible PARTIAL_MEMORY + 10 ineligible DIRTY_MEMORY windows."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            clean_ids = []
            for snap_id in (101, 102, 103):
                wid = self._insert_window(conn, tid, pid, snapshot_id=snap_id)
                clean_ids.append(wid)
            dirty_ids = []
            for snap_id in range(200, 210):
                wid = self._insert_dirty_window(conn, tid, pid, snapshot_id=snap_id)
                dirty_ids.append(wid)
            conn.commit()
        finally:
            conn.close()
        return tid, pid, clean_ids, dirty_ids

    def test_mixed_batch_completes(self):
        self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        self.assertEqual(r["lane_k_status"], LANE_K_STATUS_COMPLETED)

    def test_mixed_batch_promotes_only_clean_windows(self):
        """3 clean + 10 dirty → clean_memory_rows_created == 3."""
        _, _, clean_ids, _ = self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        self.assertEqual(r["clean_memory_rows_created"], 3)
        self.assertEqual(r["e2z_created_count"], 3)

    def test_mixed_batch_creates_episodes_only_for_clean(self):
        """Only clean window IDs get a CLEAN_MEMORY episode row."""
        _, _, clean_ids, dirty_ids = self._make_mixed_three_clean_ten_dirty()
        self._run()
        conn = self._connect()
        try:
            for wid in clean_ids:
                count = conn.execute(
                    "SELECT COUNT(*) FROM printer_episodes"
                    " WHERE memory_window_id = ? AND memory_status = 'CLEAN_MEMORY'",
                    (wid,),
                ).fetchone()[0]
                self.assertEqual(count, 1, f"clean window {wid} must have 1 episode")
            for wid in dirty_ids:
                count = conn.execute(
                    "SELECT COUNT(*) FROM printer_episodes"
                    " WHERE memory_window_id = ?",
                    (wid,),
                ).fetchone()[0]
                self.assertEqual(count, 0, f"dirty window {wid} must have 0 episodes")
        finally:
            conn.close()

    def test_mixed_batch_dirty_windows_remain_dirty(self):
        """Dirty windows must not have their memory_status changed to CLEAN_MEMORY."""
        _, _, _, dirty_ids = self._make_mixed_three_clean_ten_dirty()
        self._run()
        conn = self._connect()
        try:
            for wid in dirty_ids:
                row = conn.execute(
                    "SELECT memory_status FROM printer_memory_windows WHERE id = ?",
                    (wid,),
                ).fetchone()
                self.assertIsNotNone(row)
                self.assertNotEqual(
                    row[0], "CLEAN_MEMORY",
                    f"dirty window {wid} memory_status must not be CLEAN_MEMORY"
                )
        finally:
            conn.close()

    def test_mixed_batch_e2y_gate_reported_as_failed(self):
        """E2Y batch gate reports False (informational) for mixed batch."""
        self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        self.assertIs(r["e2y_set_gate_passed"], False)

    def test_mixed_batch_zero_clean_still_valid(self):
        self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        self.assertIs(r["zero_clean_memories_valid"], True)

    def test_do_not_train_window_never_promoted(self):
        """do_not_train=1 window in an otherwise eligible batch is excluded."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            # 3 clean windows
            for snap_id in (301, 302, 303):
                self._insert_window(conn, tid, pid, snapshot_id=snap_id)
            # 1 do_not_train window that must not become clean
            dnt_id = self._insert_do_not_train_window(conn, tid, pid, snapshot_id=304)
            conn.commit()
        finally:
            conn.close()
        before_ep = self._count("printer_episodes")
        self._run()
        conn = self._connect()
        try:
            ep_count = conn.execute(
                "SELECT COUNT(*) FROM printer_episodes WHERE memory_window_id = ?",
                (dnt_id,),
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(ep_count, 0, "do_not_train window must never get an episode")

    def test_hard_locks_unchanged_with_mixed_batch(self):
        self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        for key, val in r["hard_locks"].items():
            self.assertIs(val, True, f"hard_lock '{key}' must be True")

    def test_no_retrieval_in_mixed_batch(self):
        self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        self.assertIs(r["retrieval_activated"], False)

    def test_no_paper_decisions_in_mixed_batch(self):
        self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_no_positions_in_mixed_batch(self):
        self._make_mixed_three_clean_ten_dirty()
        r = self._run()
        self.assertEqual(r["positions_created"], 0)

    def test_idempotent_rerun_on_mixed_batch(self):
        """Second run creates zero new episodes (all already_exists)."""
        self._make_mixed_three_clean_ten_dirty()
        self._run()
        r2 = self._run()
        self.assertEqual(r2["e2z_created_count"], 0)
        self.assertEqual(r2["e2z_already_exists_count"], 3)
        self.assertEqual(r2["clean_memory_rows_created"], 0)

    def test_e2z_gate_still_blocks_ineligible_windows(self):
        """E2Z per-window gate blocks windows failing individual eligibility.

        Window with memory_status=DIRTY_MEMORY is not in E2X review_candidate_ids
        so it never reaches E2Z. This tests that if somehow such a window were
        in the eligible set, E2Z would reject it.
        """
        from printer_v1.operator_cli.e2z_clean_memory_creation import (
            E2Z_STATUS_BLOCKED as _E2Z_BLOCKED,
            create_clean_memory_from_window,
        )
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            dirty_id = self._insert_dirty_window(conn, tid, pid, snapshot_id=999)
            conn.commit()
        finally:
            conn.close()
        result = create_clean_memory_from_window(
            self.db_path, dirty_id,
            operator_approved=True,
            individual_promotion=True,  # bypass E2Y batch gate
        )
        self.assertEqual(result["e2z_status"], _E2Z_BLOCKED,
                         "E2Z per-window gate must reject a DIRTY_MEMORY window")
        self.assertFalse(result.get("created", True))

    def test_missing_critical_data_window_not_promoted(self):
        """Window with data_quality_label=MISSING_CRITICAL_DATA never becomes clean."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            self._insert_window(
                conn, tid, pid,
                memory_status="PARTIAL_MEMORY",
                memory_quality_label="PARTIAL_MEMORY",
                data_quality_label="MISSING_CRITICAL_DATA",
                do_not_train=0,
                snapshot_id=555,
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["clean_memory_rows_created"], 0)


if __name__ == "__main__":
    unittest.main()
