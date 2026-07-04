"""Lane X8 -- 5m Support Evidence Integration Tests.

Tests cover:
- Hard locks (26 locks, X8-specific additions)
- Operator gate
- Backup proof gate
- 5m support capture (capture_5m_support_evidence)
- 5m support links to correct parent WINDOW_15M token/pair window
- 5m support cannot exist as main clean memory
- 5m support cannot unlock retrieval
- 5m support cannot create paper decisions
- 5m support cannot create BUY/SELL/HOLD
- 5m support cannot create positions or PnL
- Dirty 5m support remains audit-only
- Cross-token / cross-pair linkage rejected
- Missing parent 15m window rejected
- 15m context enrichment
- Output structure
- CLI integration
- X3 lifecycle regression
- X5 five-token regression
- X6 discovery/selection regression
- Cross-lane lock consistency

All tests use fixture/temp DB only. No persistent DB mutations.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

import sqlite3

from printer_v1.db.migrate import apply_migrations
from printer_v1.operator_cli.lane_x8_5m_support_integration import (
    LANE_X8_COMMAND_NAME,
    LANE_X8_STATUS_BLOCKED,
    LANE_X8_STATUS_COMPLETED,
    _HARD_LOCKS,
    _WINDOW_15M,
    _WINDOW_5M,
    capture_5m_support_evidence,
    enrich_15m_context_with_5m_support,
    run_lane_x8_5m_support_integration,
    validate_5m_linkage_for_parent,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> tuple[tempfile.TemporaryDirectory, Path]:
    tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
    db_path = Path(tmp.name) / "printer_v1.sqlite3"
    apply_migrations(db_path)
    return tmp, db_path


def _make_backup(tmp: tempfile.TemporaryDirectory) -> Path:
    backup_path = Path(tmp.name) / "backup.sqlite3"
    backup_path.write_bytes(b"backup_proof")
    return backup_path


def _insert_token_pair(
    db_path: Path,
    mint: str,
    pair_addr: str,
) -> tuple[int, int]:
    """Insert real token + pair rows; return (token_id, pair_id)."""
    conn = sqlite3.connect(str(db_path))
    try:
        existing_tok = conn.execute(
            "SELECT id FROM printer_tokens WHERE token_mint = ?", (mint,)
        ).fetchone()
        if existing_tok:
            token_id = int(existing_tok[0])
        else:
            token_id = int(conn.execute(
                "INSERT INTO printer_tokens (token_mint, chain) VALUES (?, 'solana')",
                (mint,),
            ).lastrowid)

        existing_pair = conn.execute(
            "SELECT id FROM printer_pairs WHERE pair_address = ?", (pair_addr,)
        ).fetchone()
        if existing_pair:
            pair_id = int(existing_pair[0])
        else:
            pair_id = int(conn.execute(
                "INSERT INTO printer_pairs (token_id, pair_address) VALUES (?, ?)",
                (token_id, pair_addr),
            ).lastrowid)

        conn.commit()
        return token_id, pair_id
    finally:
        conn.close()


def _insert_15m_window(db_path: Path, token_id: int, pair_id: int) -> int:
    """Insert a WINDOW_15M row and return its id.

    token_id and pair_id must already exist in printer_tokens / printer_pairs.
    Insert without FK enforcement so we can use arbitrary IDs when needed.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = OFF")
    now = "2026-07-04T10:00:00+00:00"
    try:
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id, pair_id, "WINDOW_15M",
                now, now,
                "PARTIAL_MEMORY", "CLEAN_DATA", 0,
                "WINDOW_OPEN", "SUPPORT_EVIDENCE",
                json.dumps({"created_by": "test_setup"}), "test_setup", now, now,
            ),
        )
        window_id = int(cur.lastrowid)
        conn.commit()
        return window_id
    finally:
        conn.close()


def _setup_token_pair_and_window(
    db_path: Path,
    mint: str = "X8TestMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa",
    pair_addr: str = "X8TestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa",
) -> tuple[int, int, int]:
    """Create token, pair, and WINDOW_15M rows. Return (window_id, token_id, pair_id)."""
    token_id, pair_id = _insert_token_pair(db_path, mint, pair_addr)
    window_id = _insert_15m_window(db_path, token_id, pair_id)
    return window_id, token_id, pair_id


def _count_table(db_path: Path, table: str) -> int:
    conn = sqlite3.connect(str(db_path))
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except Exception:
        return 0
    finally:
        conn.close()


def _read_5m_row(db_path: Path, window_5m_id: int) -> dict:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute(
            "SELECT * FROM printer_memory_windows WHERE id = ?",
            (window_5m_id,),
        ).fetchone()
        return dict(row) if row else {}
    finally:
        conn.close()


# ===========================================================================
# 1. TestLaneX8HardLocks
# ===========================================================================

class TestLaneX8HardLocks(unittest.TestCase):

    def test_hard_lock_count_is_26(self):
        self.assertEqual(len(_HARD_LOCKS), 26)

    def test_no_buy_sell_hold(self):
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_no_paper_decisions(self):
        self.assertTrue(_HARD_LOCKS["no_paper_decisions"])

    def test_no_positions(self):
        self.assertTrue(_HARD_LOCKS["no_positions"])

    def test_no_pnl(self):
        self.assertTrue(_HARD_LOCKS["no_pnl"])

    def test_no_retrieval_activation(self):
        self.assertTrue(_HARD_LOCKS["no_retrieval_activation"])

    def test_no_live_trading(self):
        self.assertTrue(_HARD_LOCKS["no_live_trading"])

    def test_no_paid_api(self):
        self.assertTrue(_HARD_LOCKS["no_paid_api"])

    def test_no_5m_main_window(self):
        self.assertTrue(_HARD_LOCKS["no_5m_main_window"])

    def test_no_discovery_automation(self):
        self.assertTrue(_HARD_LOCKS["no_discovery_automation"])

    def test_x8_specific_no_5m_clean_memory(self):
        self.assertIn("no_5m_clean_memory", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_5m_clean_memory"])

    def test_x8_specific_no_x5_weakening(self):
        self.assertIn("no_x5_weakening", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_x5_weakening"])

    def test_all_locks_are_true(self):
        for name, val in _HARD_LOCKS.items():
            with self.subTest(lock=name):
                self.assertTrue(val)


# ===========================================================================
# 2. TestLaneX8OperatorGate
# ===========================================================================

class TestLaneX8OperatorGate(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.backup = _make_backup(self._tmp)
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_blocked_without_operator_approved(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=False,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertEqual(result["lane_x8_status"], LANE_X8_STATUS_BLOCKED)

    def test_operator_approved_required_message(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=False,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        reasons = " ".join(result["blocked_reasons"])
        self.assertIn("operator_approved", reasons)

    def test_completed_with_operator_approved(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertEqual(result["lane_x8_status"], LANE_X8_STATUS_COMPLETED)

    def test_capture_blocked_without_operator_approved(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=False,
        )
        self.assertFalse(result["captured"])

    def test_hard_locks_present_in_blocked_result(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=False,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertIn("hard_locks", result)
        self.assertEqual(len(result["hard_locks"]), 26)


# ===========================================================================
# 3. TestLaneX8BackupProofGate
# ===========================================================================

class TestLaneX8BackupProofGate(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_blocked_without_backup_proof_path(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, None,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertEqual(result["lane_x8_status"], LANE_X8_STATUS_BLOCKED)

    def test_blocked_when_backup_proof_missing(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, "/no/such/backup.sqlite3",
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertEqual(result["lane_x8_status"], LANE_X8_STATUS_BLOCKED)
        reasons = " ".join(result["blocked_reasons"])
        self.assertIn("backup_proof_path", reasons)

    def test_completed_when_backup_proof_exists(self):
        backup = _make_backup(self._tmp)
        result = run_lane_x8_5m_support_integration(
            self.db_path, backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertEqual(result["lane_x8_status"], LANE_X8_STATUS_COMPLETED)


# ===========================================================================
# 4. TestLaneX8Capture
# ===========================================================================

class TestLaneX8Capture(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.backup = _make_backup(self._tmp)
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_capture_succeeds(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        self.assertTrue(result["captured"])
        self.assertEqual(result["lane_x8_capture_status"], LANE_X8_STATUS_COMPLETED)

    def test_capture_writes_5m_row(self):
        before = _count_table(self.db_path, "printer_memory_windows")
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        after = _count_table(self.db_path, "printer_memory_windows")
        self.assertEqual(after, before + 1)

    def test_captured_row_has_window_5m_kind(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        row = _read_5m_row(self.db_path, result["window_5m_id"])
        self.assertEqual(row["window_kind"], _WINDOW_5M)

    def test_captured_row_token_pair_correct(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        row = _read_5m_row(self.db_path, result["window_5m_id"])
        self.assertEqual(int(row["token_id"]), self.token_id)
        self.assertEqual(int(row["pair_id"]), self.pair_id)

    def test_captured_row_window_id_returned(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        self.assertIsNotNone(result["window_5m_id"])
        self.assertIsInstance(result["window_5m_id"], int)

    def test_captured_row_context_has_parent_window_id(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        row = _read_5m_row(self.db_path, result["window_5m_id"])
        ctx = json.loads(row["supporting_context_json"])
        self.assertEqual(ctx["parent_window_id"], self.parent_id)

    def test_captured_row_context_has_parent_window_kind(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        row = _read_5m_row(self.db_path, result["window_5m_id"])
        ctx = json.loads(row["supporting_context_json"])
        self.assertEqual(ctx["parent_window_kind"], _WINDOW_15M)

    def test_multiple_captures_same_parent(self):
        # Start count is 1 (the parent 15m window)
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        # 1 parent + 2 support = 3
        count = _count_table(self.db_path, "printer_memory_windows")
        self.assertEqual(count, 3)


# ===========================================================================
# 5. TestLaneX8LinkageValidation
# ===========================================================================

class TestLaneX8LinkageValidation(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )
        # A different, non-existent ID pair for cross-* tests
        self.other_token_id = self.token_id + 500
        self.other_pair_id = self.pair_id + 500

    def tearDown(self):
        self._tmp.cleanup()

    def _conn(self) -> sqlite3.Connection:
        c = sqlite3.connect(str(self.db_path))
        c.row_factory = sqlite3.Row
        return c

    def test_valid_linkage_passes(self):
        with self._conn() as conn:
            result = validate_5m_linkage_for_parent(
                conn, self.parent_id, self.token_id, self.pair_id
            )
        self.assertTrue(result["valid"])
        self.assertIsNone(result["blocked_reason"])

    def test_missing_parent_rejected(self):
        with self._conn() as conn:
            result = validate_5m_linkage_for_parent(conn, 99999, self.token_id, self.pair_id)
        self.assertFalse(result["valid"])
        self.assertIn("99999", result["blocked_reason"])

    def test_wrong_window_kind_rejected(self):
        # Insert a WINDOW_5M parent (wrong kind) — FK off for this helper
        conn2 = sqlite3.connect(str(self.db_path))
        conn2.execute("PRAGMA foreign_keys = OFF")
        now = "2026-07-04T10:00:00+00:00"
        cur = conn2.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.token_id, self.pair_id, _WINDOW_5M, now, now,
                "PARTIAL_MEMORY", "CLEAN_DATA", 0,
                "WINDOW_CLOSED", "SUPPORT_EVIDENCE",
                "{}", "test", now, now,
            ),
        )
        bad_id = int(cur.lastrowid)
        conn2.commit()
        conn2.close()

        with self._conn() as conn:
            result = validate_5m_linkage_for_parent(
                conn, bad_id, self.token_id, self.pair_id
            )
        self.assertFalse(result["valid"])
        self.assertIn(_WINDOW_5M, result["blocked_reason"])

    def test_cross_token_rejected(self):
        with self._conn() as conn:
            result = validate_5m_linkage_for_parent(
                conn, self.parent_id, self.other_token_id, self.pair_id
            )
        self.assertFalse(result["valid"])
        self.assertIn("cross-token", result["blocked_reason"])

    def test_cross_pair_rejected(self):
        with self._conn() as conn:
            result = validate_5m_linkage_for_parent(
                conn, self.parent_id, self.token_id, self.other_pair_id
            )
        self.assertFalse(result["valid"])
        self.assertIn("cross-pair", result["blocked_reason"])

    def test_valid_linkage_returns_parent_kind(self):
        with self._conn() as conn:
            result = validate_5m_linkage_for_parent(
                conn, self.parent_id, self.token_id, self.pair_id
            )
        self.assertEqual(result["parent_window_kind"], _WINDOW_15M)


# ===========================================================================
# 6. TestLaneX8NoCleanMemory
# ===========================================================================

class TestLaneX8NoCleanMemory(unittest.TestCase):
    """5m support cannot produce CLEAN_MEMORY under any circumstances."""

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_clean_data_produces_support_evidence_not_clean_memory(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
            data_quality_label="CLEAN_DATA",
            source_status="COMPLETE",
        )
        self.assertNotEqual(result["memory_quality_label"], "CLEAN_MEMORY")
        self.assertEqual(result["memory_quality_label"], "SUPPORT_EVIDENCE")

    def test_captured_row_memory_status_is_not_clean_memory(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        row = _read_5m_row(self.db_path, result["window_5m_id"])
        self.assertNotIn(row["memory_status"], ("CLEAN_MEMORY",))

    def test_capture_result_5m_clean_memory_blocked_flag(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        self.assertTrue(result["5m_clean_memory_blocked"])

    def test_run_result_5m_clean_memory_blocked_flag(self):
        backup = _make_backup(self._tmp)
        result = run_lane_x8_5m_support_integration(
            self.db_path, backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertTrue(result["5m_clean_memory_blocked"])

    def test_no_5m_clean_memory_lock_present(self):
        self.assertIn("no_5m_clean_memory", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_5m_clean_memory"])

    def test_printer_memories_not_written(self):
        before = _count_table(self.db_path, "printer_memories")
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        after = _count_table(self.db_path, "printer_memories")
        self.assertEqual(before, after)

    def test_5m_main_window_blocked_flag_in_capture_result(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        self.assertTrue(result["5m_main_window_blocked"])


# ===========================================================================
# 7. TestLaneX8NoRetrieval
# ===========================================================================

class TestLaneX8NoRetrieval(unittest.TestCase):
    """5m support cannot unlock retrieval."""

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.backup = _make_backup(self._tmp)
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_retrieval_from_5m_blocked_flag(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertTrue(result["retrieval_from_5m_blocked"])

    def test_no_retrieval_activation_lock(self):
        self.assertTrue(_HARD_LOCKS["no_retrieval_activation"])

    def test_retrieval_tables_not_written(self):
        for table in (
            "printer_retrieval_candidates",
            "printer_retrieval_results",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
        ):
            before = _count_table(self.db_path, table)
            capture_5m_support_evidence(
                self.db_path, self.parent_id, self.token_id, self.pair_id,
                operator_approved=True,
            )
            after = _count_table(self.db_path, table)
            with self.subTest(table=table):
                self.assertEqual(before, after)

    def test_retrieval_blocked_in_enrich_result(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        enrich = result["enrich_result"]
        self.assertIsNotNone(enrich)
        self.assertTrue(enrich["retrieval_from_5m_blocked"])

    def test_retrieval_blocked_in_support_entries(self):
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        for entry in result["support_entries"]:
            with self.subTest(entry_id=entry["id"]):
                self.assertTrue(entry["retrieval_blocked"])


# ===========================================================================
# 8. TestLaneX8NoPaperDecisionsOrBuy
# ===========================================================================

class TestLaneX8NoPaperDecisionsOrBuy(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.backup = _make_backup(self._tmp)
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_paper_decision_from_5m_blocked_flag(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertTrue(result["paper_decision_from_5m_blocked"])

    def test_buy_from_5m_blocked_flag(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertTrue(result["buy_from_5m_blocked"])

    def test_no_buy_sell_hold_lock(self):
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_no_paper_decisions_lock(self):
        self.assertTrue(_HARD_LOCKS["no_paper_decisions"])

    def test_paper_tables_not_written(self):
        for table in (
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        ):
            before = _count_table(self.db_path, table)
            capture_5m_support_evidence(
                self.db_path, self.parent_id, self.token_id, self.pair_id,
                operator_approved=True,
            )
            after = _count_table(self.db_path, table)
            with self.subTest(table=table):
                self.assertEqual(before, after)

    def test_no_pnl_no_positions_locks(self):
        self.assertTrue(_HARD_LOCKS["no_positions"])
        self.assertTrue(_HARD_LOCKS["no_pnl"])


# ===========================================================================
# 9. TestLaneX8DirtyAuditOnly
# ===========================================================================

class TestLaneX8DirtyAuditOnly(unittest.TestCase):
    """Dirty/stale/failed/mismatched 5m evidence stays audit-only."""

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_stale_evidence_is_dirty_memory(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, is_stale=True,
        )
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertTrue(result["do_not_train"])

    def test_failed_evidence_is_dirty_memory(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, is_failed=True,
        )
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertTrue(result["do_not_train"])

    def test_failed_source_status_is_dirty(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, source_status="FAILED",
        )
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertTrue(result["do_not_train"])

    def test_mismatched_evidence_is_dirty(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, is_mismatched=True,
        )
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertTrue(result["do_not_train"])

    def test_dirty_data_label_is_dirty(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, data_quality_label="DIRTY_DATA",
        )
        self.assertEqual(result["memory_quality_label"], "DIRTY_MEMORY")
        self.assertTrue(result["do_not_train"])

    def test_incomplete_evidence_is_audit_only(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, is_incomplete=True,
        )
        self.assertEqual(result["memory_quality_label"], "AUDIT_ONLY")
        self.assertTrue(result["do_not_train"])

    def test_dirty_row_do_not_train_set(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, is_stale=True,
        )
        row = _read_5m_row(self.db_path, result["window_5m_id"])
        self.assertEqual(int(row["do_not_train"]), 1)

    def test_dirty_classified_in_enrich(self):
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True, is_stale=True,
        )
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        self.assertGreater(result["dirty_support_count"], 0)
        self.assertEqual(result["valid_support_count"], 0)
        self.assertEqual(result["enrichment_status"], "PARTIAL")


# ===========================================================================
# 10. TestLaneX8CrossPairRejected
# ===========================================================================

class TestLaneX8CrossPairRejected(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )
        # Invalid IDs that don't exist in the DB and don't match the parent
        self.wrong_token_id = self.token_id + 500
        self.wrong_pair_id = self.pair_id + 500

    def tearDown(self):
        self._tmp.cleanup()

    def test_cross_token_capture_blocked(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.wrong_token_id, self.pair_id,
            operator_approved=True,
        )
        self.assertFalse(result["captured"])
        self.assertEqual(result["lane_x8_capture_status"], LANE_X8_STATUS_BLOCKED)

    def test_cross_token_reason_in_blocked(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.wrong_token_id, self.pair_id,
            operator_approved=True,
        )
        reasons = " ".join(result["blocked_reasons"])
        self.assertIn("cross-token", reasons)

    def test_cross_pair_capture_blocked(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.wrong_pair_id,
            operator_approved=True,
        )
        self.assertFalse(result["captured"])
        self.assertEqual(result["lane_x8_capture_status"], LANE_X8_STATUS_BLOCKED)

    def test_cross_pair_reason_in_blocked(self):
        result = capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.wrong_pair_id,
            operator_approved=True,
        )
        reasons = " ".join(result["blocked_reasons"])
        self.assertIn("cross-pair", reasons)

    def test_cross_pair_no_5m_row_written(self):
        before = _count_table(self.db_path, "printer_memory_windows")
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.wrong_pair_id,
            operator_approved=True,
        )
        after = _count_table(self.db_path, "printer_memory_windows")
        self.assertEqual(before, after)


# ===========================================================================
# 11. TestLaneX8MissingParent
# ===========================================================================

class TestLaneX8MissingParent(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_parent_capture_blocked(self):
        result = capture_5m_support_evidence(
            self.db_path, 99999, 1, 1, operator_approved=True,
        )
        self.assertFalse(result["captured"])
        self.assertEqual(result["lane_x8_capture_status"], LANE_X8_STATUS_BLOCKED)

    def test_missing_parent_reason_in_blocked(self):
        result = capture_5m_support_evidence(
            self.db_path, 99999, 1, 1, operator_approved=True,
        )
        reasons = " ".join(result["blocked_reasons"])
        self.assertIn("99999", reasons)

    def test_missing_parent_no_5m_row_written(self):
        before = _count_table(self.db_path, "printer_memory_windows")
        capture_5m_support_evidence(
            self.db_path, 99999, 1, 1, operator_approved=True,
        )
        after = _count_table(self.db_path, "printer_memory_windows")
        self.assertEqual(before, after)

    def test_enrich_with_missing_parent_returns_unenriched(self):
        result = enrich_15m_context_with_5m_support(
            self.db_path, 99999, 1, 1
        )
        self.assertEqual(result["enrichment_status"], "UNENRICHED")
        self.assertFalse(result["parent_found"])

    def test_enrich_missing_parent_safety_flags_still_set(self):
        result = enrich_15m_context_with_5m_support(
            self.db_path, 99999, 1, 1
        )
        self.assertTrue(result["5m_clean_memory_blocked"])
        self.assertTrue(result["retrieval_from_5m_blocked"])


# ===========================================================================
# 12. TestLaneX8Enrichment
# ===========================================================================

class TestLaneX8Enrichment(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_enrich_no_5m_is_unenriched(self):
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        self.assertEqual(result["enrichment_status"], "UNENRICHED")
        self.assertEqual(result["support_5m_count"], 0)

    def test_enrich_after_capture_is_enriched(self):
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        self.assertEqual(result["enrichment_status"], "ENRICHED")
        self.assertEqual(result["valid_support_count"], 1)

    def test_enrich_returns_parent_window(self):
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        self.assertTrue(result["parent_found"])
        self.assertEqual(result["parent_window"]["window_kind"], _WINDOW_15M)

    def test_enrich_15m_clean_memory_unaffected(self):
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        self.assertTrue(result["15m_clean_memory_unaffected"])

    def test_enrich_support_entries_have_correct_fields(self):
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        entry = result["support_entries"][0]
        self.assertIn("id", entry)
        self.assertIn("classification", entry)
        self.assertIn("memory_quality_label", entry)
        self.assertIn("5m_clean_memory_blocked", entry)

    def test_enrich_multiple_5m_rows(self):
        for _ in range(3):
            capture_5m_support_evidence(
                self.db_path, self.parent_id, self.token_id, self.pair_id,
                operator_approved=True,
            )
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        self.assertEqual(result["support_5m_count"], 3)
        self.assertEqual(result["valid_support_count"], 3)

    def test_enrich_only_sees_own_parent_not_other_parents(self):
        # Create a second parent window with the same token/pair
        parent_id_b = _insert_15m_window(self.db_path, self.token_id, self.pair_id)
        # Capture for parent_id_b only
        capture_5m_support_evidence(
            self.db_path, parent_id_b, self.token_id, self.pair_id,
            operator_approved=True,
        )
        # Enrich for self.parent_id should see 0 entries
        result = enrich_15m_context_with_5m_support(
            self.db_path, self.parent_id, self.token_id, self.pair_id
        )
        self.assertEqual(result["support_5m_count"], 0)


# ===========================================================================
# 13. TestLaneX8OutputStructure
# ===========================================================================

class TestLaneX8OutputStructure(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.backup = _make_backup(self._tmp)
        self.parent_id, self.token_id, self.pair_id = _setup_token_pair_and_window(
            self.db_path
        )

    def tearDown(self):
        self._tmp.cleanup()

    def test_completed_result_has_command(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertEqual(result["command"], LANE_X8_COMMAND_NAME)

    def test_completed_result_has_lane_x8_status(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertIn("lane_x8_status", result)

    def test_completed_result_has_capture_and_enrich(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertIn("capture_result", result)
        self.assertIn("enrich_result", result)

    def test_blocked_result_has_empty_results(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=False,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertIsNone(result["capture_result"])
        self.assertIsNone(result["enrich_result"])

    def test_enrich_only_mode(self):
        capture_5m_support_evidence(
            self.db_path, self.parent_id, self.token_id, self.pair_id,
            operator_approved=True,
        )
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
            capture=False, enrich=True,
        )
        self.assertEqual(result["lane_x8_status"], LANE_X8_STATUS_COMPLETED)
        self.assertIsNone(result["capture_result"])
        self.assertIsNotNone(result["enrich_result"])
        self.assertEqual(result["enrich_result"]["valid_support_count"], 1)

    def test_hard_locks_in_result(self):
        result = run_lane_x8_5m_support_integration(
            self.db_path, self.backup,
            operator_approved=True,
            parent_window_id=self.parent_id,
            token_id=self.token_id, pair_id=self.pair_id,
        )
        self.assertIn("hard_locks", result)
        self.assertEqual(len(result["hard_locks"]), 26)


# ===========================================================================
# 14. TestLaneX8CLI
# ===========================================================================

class TestLaneX8CLI(unittest.TestCase):

    def setUp(self):
        self._tmp, self.db_path = _make_db()
        self.backup = _make_backup(self._tmp)

    def tearDown(self):
        self._tmp.cleanup()

    def test_cli_blocked_without_operator_approved(self):
        from printer_v1.operator_cli.commands import (
            main_run_lane_x8_5m_support_integration,
        )
        rc = main_run_lane_x8_5m_support_integration([
            "--db-path", str(self.db_path),
            "--backup-proof-path", str(self.backup),
        ])
        self.assertEqual(rc, 0)

    def test_cli_command_name_constant(self):
        self.assertEqual(
            LANE_X8_COMMAND_NAME, "printer-run-lane-x8-5m-support-integration"
        )

    def test_cli_returns_zero_on_blocked(self):
        from printer_v1.operator_cli.commands import (
            main_run_lane_x8_5m_support_integration,
        )
        rc = main_run_lane_x8_5m_support_integration([
            "--db-path", str(self.db_path),
            "--backup-proof-path", str(self.backup),
        ])
        self.assertEqual(rc, 0)

    def test_cli_json_output_is_valid(self):
        from printer_v1.operator_cli.commands import (
            main_run_lane_x8_5m_support_integration,
        )
        old_stdout = sys.stdout
        sys.stdout = StringIO()
        try:
            main_run_lane_x8_5m_support_integration([
                "--db-path", str(self.db_path),
                "--backup-proof-path", str(self.backup),
            ])
            output = sys.stdout.getvalue()
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(output)
        self.assertIn("lane_x8_status", parsed)


# ===========================================================================
# 15. TestLaneX8X3Regression
# ===========================================================================

class TestLaneX8X3Regression(unittest.TestCase):
    """X3 lifecycle still works after X8 introduction."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_x3_hard_locks_count_is_23(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            _HARD_LOCKS as X3_LOCKS,
        )
        self.assertEqual(len(X3_LOCKS), 23)

    def test_x3_cooldown_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            enter_cooldown_after_window,
        )
        result = enter_cooldown_after_window(
            self.db_path,
            "X8TestMintX3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa",
            "X8TestPairX3AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa",
        )
        self.assertIn(result["lane_x3_status"], (
            "LANE_X3_COOLDOWN_ENTERED", "LANE_X3_NO_ACTION", "LANE_X3_BLOCKED",
        ))

    def test_x3_gate_passes_for_queued_token(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            check_x3_cooldown_gate,
        )
        # Fresh token not in cooldown — gate returns empty list (clear)
        blocked = check_x3_cooldown_gate(
            self.db_path,
            ["X8GateMintX3BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBb"],
        )
        self.assertIsInstance(blocked, list)
        self.assertEqual(blocked, [])

    def test_x3_reopen_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            enter_cooldown_after_window,
            reopen_token,
        )
        enter_cooldown_after_window(
            self.db_path,
            "X8ReopenMintX3CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCc",
            "X8ReopenPairX3CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCc",
        )
        result = reopen_token(
            self.db_path,
            "X8ReopenMintX3CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCc",
            "X8ReopenPairX3CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCc",
        )
        self.assertIn(result["lane_x3_status"], (
            "LANE_X3_REOPENED", "LANE_X3_NO_ACTION", "LANE_X3_BLOCKED",
        ))

    def test_x3_archive_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            archive_after_memory_window,
        )
        result = archive_after_memory_window(
            self.db_path,
            "X8ArchiveMintX3DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDd",
            "X8ArchivePairX3DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDd",
        )
        self.assertIn(result["lane_x3_status"], (
            "LANE_X3_ARCHIVED", "LANE_X3_NO_ACTION", "LANE_X3_BLOCKED",
        ))


# ===========================================================================
# 16. TestLaneX8X5Regression
# ===========================================================================

class TestLaneX8X5Regression(unittest.TestCase):
    """X5 five-token runner behavior not weakened by X8."""

    def test_x5_hard_locks_count_is_24(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            _HARD_LOCKS as X5_LOCKS,
        )
        self.assertEqual(len(X5_LOCKS), 24)

    def test_x5_no_5m_main_window_lock(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            _HARD_LOCKS as X5_LOCKS,
        )
        self.assertTrue(X5_LOCKS["no_5m_main_window"])

    def test_x5_exact_token_count_unchanged(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            LANE_X5_EXACT_TOKEN_COUNT,
        )
        self.assertEqual(LANE_X5_EXACT_TOKEN_COUNT, 5)

    def test_x5_validator_rejects_four_tokens(self):
        import os
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            _load_and_validate_five_token_list,
        )
        data = {
            "tokens": [
                {
                    "token_mint": f"X8TestMint{i}",
                    "pair_address": f"X8TestPair{i}",
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                }
                for i in range(4)
            ]
        }
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".json", delete=False
        ) as f:
            json.dump(data, f)
            fname = f.name
        try:
            valid, reason, *_ = _load_and_validate_five_token_list(fname)
        finally:
            os.unlink(fname)
        self.assertFalse(valid)
        self.assertIn("5", reason)

    def test_x5_command_name_unchanged(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import LANE_X5_COMMAND_NAME
        self.assertEqual(LANE_X5_COMMAND_NAME, "printer-run-lane-x5-five-token-cycle")

    def test_x5_window_kind_is_15m_only(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            _ENABLED_MAIN_WINDOW_KIND,
            _FORBIDDEN_AS_MAIN_WINDOW,
        )
        self.assertEqual(_ENABLED_MAIN_WINDOW_KIND, "WINDOW_15M")
        self.assertIn("WINDOW_5M_MICRO_EVENT", _FORBIDDEN_AS_MAIN_WINDOW)


# ===========================================================================
# 17. TestLaneX8X6Regression
# ===========================================================================

class TestLaneX8X6Regression(unittest.TestCase):
    """X6 discovery/selection behavior not weakened by X8."""

    def test_x6_hard_locks_count_is_24(self):
        from printer_v1.operator_cli.lane_x6_discovery_selection_repair import (
            _HARD_LOCKS as X6_LOCKS,
        )
        self.assertEqual(len(X6_LOCKS), 24)

    def test_x6_no_discovery_automation_lock(self):
        from printer_v1.operator_cli.lane_x6_discovery_selection_repair import (
            _HARD_LOCKS as X6_LOCKS,
        )
        self.assertTrue(X6_LOCKS["no_discovery_automation"])

    def test_x6_diet_labels_intact(self):
        from printer_v1.operator_cli.lane_x6_discovery_selection_repair import (
            ALL_DIET_LABELS,
        )
        self.assertEqual(len(ALL_DIET_LABELS), 9)

    def test_x6_dedup_by_mint_still_works(self):
        from printer_v1.operator_cli.lane_x6_discovery_selection_repair import dedup_by_mint
        candidates = [
            {"token_mint": "MintA", "pair_address": "PairA1",
             "captured_at": "2026-01-01T00:00:00+00:00"},
            {"token_mint": "MintA", "pair_address": "PairA2",
             "captured_at": "2026-01-02T00:00:00+00:00"},
        ]
        kept, collapsed = dedup_by_mint(candidates)
        self.assertEqual(len(kept), 1)
        self.assertEqual(len(collapsed), 1)

    def test_x6_select_candidates_blocked_without_approval(self):
        from printer_v1.operator_cli.lane_x6_discovery_selection_repair import (
            select_candidates_for_memory_growth,
        )
        tmp, db_path = _make_db()
        backup = _make_backup(tmp)
        try:
            result = select_candidates_for_memory_growth(
                db_path, backup, operator_approved=False
            )
            self.assertEqual(result["lane_x6_status"], "LANE_X6_BLOCKED")
        finally:
            tmp.cleanup()


# ===========================================================================
# 18. TestLaneX8CrossLaneLocks
# ===========================================================================

class TestLaneX8CrossLaneLocks(unittest.TestCase):
    """Verify lock consistency across X3/X5/X6/X8."""

    def test_x8_has_no_5m_clean_memory(self):
        self.assertIn("no_5m_clean_memory", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_5m_clean_memory"])

    def test_all_shared_locks_present_in_x8_and_x3(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            _HARD_LOCKS as X3_LOCKS,
        )
        shared = {
            "no_buy_sell_hold", "no_paper_decisions", "no_positions", "no_pnl",
            "no_retrieval_activation", "no_live_trading", "no_paid_api",
            "no_wallet_private_key", "no_generic_search", "no_unbounded_loop",
            "no_daemon_mode", "no_scheduler_bypass", "no_source_governor_bypass",
            "no_ad_hoc_api_loop", "no_direct_adapter_call",
            "no_scoring_ranking_confidence", "no_embeddings_vectors",
            "no_1h_4h_12h_24h_collection", "no_5m_main_window", "no_trade_events",
            "no_paper_trade_audits", "no_token_pair_mixing",
        }
        for lock in shared:
            with self.subTest(lock=lock):
                self.assertTrue(_HARD_LOCKS.get(lock, False))
                self.assertTrue(X3_LOCKS.get(lock, False))

    def test_x8_lock_count_exceeds_x3_x5_x6(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            _HARD_LOCKS as X3_LOCKS,
        )
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            _HARD_LOCKS as X5_LOCKS,
        )
        from printer_v1.operator_cli.lane_x6_discovery_selection_repair import (
            _HARD_LOCKS as X6_LOCKS,
        )
        self.assertGreater(len(_HARD_LOCKS), len(X3_LOCKS))
        self.assertGreater(len(_HARD_LOCKS), len(X5_LOCKS))
        self.assertGreaterEqual(len(_HARD_LOCKS), len(X6_LOCKS))

    def test_x8_no_x5_weakening_lock_present(self):
        self.assertTrue(_HARD_LOCKS["no_x5_weakening"])

    def test_x5_window_5m_still_support_only_in_x5(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            _SUPPORT_ONLY_WINDOW_KINDS,
        )
        self.assertIn("WINDOW_5M_MICRO_EVENT", _SUPPORT_ONLY_WINDOW_KINDS)

    def test_run_result_safety_flags_consistent(self):
        tmp, db_path = _make_db()
        backup = _make_backup(tmp)
        try:
            result = run_lane_x8_5m_support_integration(
                db_path, backup,
                operator_approved=False,
                parent_window_id=1, token_id=1, pair_id=1,
            )
            self.assertTrue(result["5m_main_window_blocked"])
            self.assertTrue(result["5m_clean_memory_blocked"])
            self.assertTrue(result["retrieval_from_5m_blocked"])
            self.assertTrue(result["paper_decision_from_5m_blocked"])
            self.assertTrue(result["buy_from_5m_blocked"])
            self.assertTrue(result["position_from_5m_blocked"])
        finally:
            tmp.cleanup()


if __name__ == "__main__":
    unittest.main()
