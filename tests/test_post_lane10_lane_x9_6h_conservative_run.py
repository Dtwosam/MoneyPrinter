"""Tests for Lane X9 — 6h Conservative 15m Memory Growth Run.

Requirements verified:
  1. 6h outer bound enforced
  2. Repeated 3-5 asset batches supported
  3. Up to 5 WINDOW_15M cycles per batch before review/rotation reporting
  4. 5 x 15m does NOT automatically create clean memory
  5. Zero-clean batch is valid
  6. WINDOW_15M main-only
  7. 5m support-only (WINDOW_5M_MICRO_EVENT never a main tracking window)
  8. No silent replacement — new batch requires operator approval
  9. No retrieval / paper / BUY / position / PnL unlock
  10. 26 hard locks present and True
  11. No PRAGMA foreign_keys = OFF in production module
  12. No synthetic memory-window writer in production module
"""

from __future__ import annotations

import inspect
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from typing import Any

from printer_v1.db.migrate import apply_migrations


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_db() -> Path:
    """Create a temp DB with all migrations applied."""
    tmp = tempfile.mktemp(suffix=".db")
    db_path = Path(tmp)
    apply_migrations(str(db_path))
    return db_path


def _make_backup(db_path: Path) -> Path:
    import shutil
    bk = Path(str(db_path) + ".bak")
    shutil.copy2(str(db_path), str(bk))
    return bk


def _insert_token(db_path: Path, mint: str) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        row = conn.execute(
            "SELECT id FROM printer_tokens WHERE token_mint = ?", (mint,)
        ).fetchone()
        if row:
            return int(row[0])
        cur = conn.execute(
            "INSERT INTO printer_tokens (token_mint, chain) VALUES (?, 'solana')", (mint,)
        )
        tid = int(cur.lastrowid)
        conn.commit()
        return tid
    finally:
        conn.close()


def _insert_pair(db_path: Path, token_id: int, pair_addr: str) -> int:
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        row = conn.execute(
            "SELECT id FROM printer_pairs WHERE pair_address = ?", (pair_addr,)
        ).fetchone()
        if row:
            return int(row[0])
        cur = conn.execute(
            "INSERT INTO printer_pairs (token_id, pair_address) VALUES (?, ?)",
            (token_id, pair_addr),
        )
        pid = int(cur.lastrowid)
        conn.commit()
        return pid
    finally:
        conn.close()


def _insert_15m_window(
    db_path: Path,
    token_id: int,
    pair_id: int,
    memory_status: str = "PARTIAL_MEMORY",
) -> int:
    """Seed one WINDOW_15M row for test fixture purposes.

    Uses real token_id/pair_id so FK enforcement is satisfied.  Tests call this
    directly; production X9 code never calls it.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")
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
                token_id, pair_id, "WINDOW_15M", now, now,
                memory_status, "CLEAN_DATA", 0,
                "WINDOW_CLOSED", memory_status,
                json.dumps({"created_by": "test_fixture"}),
                "test_fixture", now, now,
            ),
        )
        wid = int(cur.lastrowid)
        conn.commit()
        return wid
    finally:
        conn.close()


def _make_token_config(
    mint: str,
    pair_addr: str,
    operator_approved: bool = True,
) -> dict[str, Any]:
    return {
        "token_mint": mint,
        "pair_address": pair_addr,
        "chain": "solana",
        "operator_approved": operator_approved,
    }


# Canonical test mints / pairs
_MINT_A = "X9TestMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa"
_MINT_B = "X9TestMintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBb"
_MINT_C = "X9TestMintCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCc"
_PAIR_A = "X9PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAa"
_PAIR_B = "X9PairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBb"
_PAIR_C = "X9PairCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCc"


def _canonical_batch() -> list[dict[str, Any]]:
    return [
        _make_token_config(_MINT_A, _PAIR_A),
        _make_token_config(_MINT_B, _PAIR_B),
        _make_token_config(_MINT_C, _PAIR_C),
    ]


def _seed_abc(db: Path) -> tuple[int, int, int, int, int, int]:
    """Seed tokens A/B/C and return (tid_a, pid_a, tid_b, pid_b, tid_c, pid_c)."""
    tid_a = _insert_token(db, _MINT_A)
    pid_a = _insert_pair(db, tid_a, _PAIR_A)
    tid_b = _insert_token(db, _MINT_B)
    pid_b = _insert_pair(db, tid_b, _PAIR_B)
    tid_c = _insert_token(db, _MINT_C)
    pid_c = _insert_pair(db, tid_c, _PAIR_C)
    return tid_a, pid_a, tid_b, pid_b, tid_c, pid_c


# ---------------------------------------------------------------------------
# 1. Production module safety — no FK bypass, no synthetic writer
# ---------------------------------------------------------------------------

class TestX9ProductionModuleSafety(unittest.TestCase):
    def test_no_fk_bypass_in_production_module(self):
        import printer_v1.operator_cli.lane_x9_6h_conservative_run as m
        src = inspect.getsource(m)
        self.assertNotIn("foreign_keys = OFF", src,
                         "Production module must not contain PRAGMA foreign_keys = OFF")

    def test_no_synthetic_window_writer_in_production_module(self):
        import printer_v1.operator_cli.lane_x9_6h_conservative_run as m
        self.assertFalse(
            hasattr(m, "record_x9_batch_windows"),
            "record_x9_batch_windows must not exist in production module",
        )

    def test_no_import_json_in_production_module(self):
        import printer_v1.operator_cli.lane_x9_6h_conservative_run as m
        src = inspect.getsource(m)
        self.assertNotIn("import json", src,
                         "json is only needed for synthetic row creation, which was removed")

    def test_connect_helper_uses_fk_on(self):
        import printer_v1.operator_cli.lane_x9_6h_conservative_run as m
        src = inspect.getsource(m)
        self.assertIn("foreign_keys = ON", src)

    def test_report_function_is_read_only(self):
        """produce_x9_batch_report must not contain INSERT/UPDATE/DELETE."""
        import printer_v1.operator_cli.lane_x9_6h_conservative_run as m
        src = inspect.getsource(m.produce_x9_batch_report)
        for keyword in ("INSERT", "UPDATE", "DELETE"):
            self.assertNotIn(keyword, src.upper(),
                             f"produce_x9_batch_report must not contain {keyword}")


# ---------------------------------------------------------------------------
# 2. Hard lock presence
# ---------------------------------------------------------------------------

class TestX9HardLockCount(unittest.TestCase):
    def test_exactly_26_locks(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertEqual(len(_HARD_LOCKS), 26)

    def test_all_locks_are_true(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        for k, v in _HARD_LOCKS.items():
            self.assertTrue(v, f"hard lock {k!r} is not True")

    def test_no_10_token_expansion_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_10_token_expansion", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_10_token_expansion"])

    def test_no_silent_batch_replacement_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_silent_batch_replacement", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_silent_batch_replacement"])

    def test_no_1h_4h_12h_24h_collection_lock_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_1h_4h_12h_24h_collection", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_1h_4h_12h_24h_collection"])

    def test_no_retrieval_lock_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_retrieval_activation", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_retrieval_activation"])

    def test_no_paper_decisions_lock_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_paper_decisions", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_paper_decisions"])

    def test_no_buy_sell_hold_lock_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_buy_sell_hold", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_no_scoring_ranking_lock_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_scoring_ranking_confidence", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_scoring_ranking_confidence"])

    def test_no_discovery_automation_lock_present(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _HARD_LOCKS
        self.assertIn("no_discovery_automation", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_discovery_automation"])


# ---------------------------------------------------------------------------
# 3. Outer bound constants
# ---------------------------------------------------------------------------

class TestX9BoundConstants(unittest.TestCase):
    def test_max_run_seconds_is_6h(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import LANE_X9_MAX_RUN_SECONDS
        self.assertEqual(LANE_X9_MAX_RUN_SECONDS, 21600)

    def test_batch_min_tokens_is_3(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import LANE_X9_BATCH_MIN_TOKENS
        self.assertEqual(LANE_X9_BATCH_MIN_TOKENS, 3)

    def test_batch_max_tokens_is_5(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import LANE_X9_BATCH_MAX_TOKENS
        self.assertEqual(LANE_X9_BATCH_MAX_TOKENS, 5)

    def test_batch_max_cycles_is_5(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import LANE_X9_BATCH_MAX_CYCLES
        self.assertEqual(LANE_X9_BATCH_MAX_CYCLES, 5)

    def test_cycle_minutes_is_15(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import LANE_X9_CYCLE_MINUTES
        self.assertEqual(LANE_X9_CYCLE_MINUTES, 15)

    def test_batch_minutes_is_75(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import LANE_X9_BATCH_MINUTES
        self.assertEqual(LANE_X9_BATCH_MINUTES, 75)


# ---------------------------------------------------------------------------
# 4. Requirement 1: 6h outer bound enforced
# ---------------------------------------------------------------------------

class TestX9SixHourOuterBound(unittest.TestCase):
    def test_max_run_seconds_exceeds_6h_is_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        db = _make_db()
        bk = _make_backup(db)
        batch = _canonical_batch()
        result = run_x9_6h_conservative_proof(
            db, bk, batches=[batch, batch, batch],
            operator_approved=True, max_run_seconds=21601,
        )
        self.assertEqual(result["lane_x9_status"], "LANE_X9_BLOCKED")
        self.assertTrue(any("21601" in r or "6h" in r for r in result["blocked_reasons"]))

    def test_exactly_6h_allowed(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_run_config
        db = _make_db()
        bk = _make_backup(db)
        result = validate_x9_run_config(
            db, bk, [_canonical_batch()], operator_approved=True, max_run_seconds=21600
        )
        self.assertTrue(result["valid"], result["blocked_reasons"])

    def test_less_than_6h_allowed(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_run_config
        db = _make_db()
        bk = _make_backup(db)
        result = validate_x9_run_config(
            db, bk, [_canonical_batch()], operator_approved=True, max_run_seconds=3600
        )
        self.assertTrue(result["valid"], result["blocked_reasons"])

    def test_outer_bound_enforced_in_run_summary(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import (
            run_x9_6h_conservative_proof, LANE_X9_MAX_RUN_SECONDS,
        )
        db = _make_db()
        bk = _make_backup(db)
        tid_a, pid_a, tid_b, pid_b, tid_c, pid_c = _seed_abc(db)
        tids = [tid_a, tid_b, tid_c]
        pids = [pid_a, pid_b, pid_c]
        # one row per token per batch
        def _seed_batch(batch_no: int) -> list[int]:
            return [_insert_15m_window(db, t, p) for t, p in zip(tids, pids)]
        w0, w1, w2 = _seed_batch(0), _seed_batch(1), _seed_batch(2)
        result = run_x9_6h_conservative_proof(
            db, bk, batches=[_canonical_batch()] * 3,
            operator_approved=True,
            token_ids_per_batch=[tids, tids, tids],
            window_ids_per_batch=[w0, w1, w2],
        )
        self.assertFalse(result.get("blocked_reasons"))
        self.assertTrue(result["run_summary"]["outer_bound_enforced"])
        self.assertEqual(result["run_summary"]["max_run_seconds"], LANE_X9_MAX_RUN_SECONDS)


# ---------------------------------------------------------------------------
# 5. Requirement 2: repeated 3-5 asset batches supported
# ---------------------------------------------------------------------------

class TestX9RepeatedBatches(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()
        self.bk = _make_backup(self.db)
        self.tid_a, self.pid_a, self.tid_b, self.pid_b, self.tid_c, self.pid_c = (
            _seed_abc(self.db)
        )
        self.tids = [self.tid_a, self.tid_b, self.tid_c]
        self.pids = [self.pid_a, self.pid_b, self.pid_c]

    def _one_window_per_token(self) -> list[int]:
        return [_insert_15m_window(self.db, t, p) for t, p in zip(self.tids, self.pids)]

    def test_single_3_token_batch_accepted(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        result = validate_x9_batch_config(_canonical_batch(), operator_approved=True)
        self.assertTrue(result["valid"])

    def test_5_token_batch_accepted(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        mints = [f"X9MintFive{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" for i in range(5)]
        pairs = [f"X9PairFive{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" for i in range(5)]
        batch = [_make_token_config(m, p) for m, p in zip(mints, pairs)]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertTrue(result["valid"])

    def test_multiple_batches_run_produces_multiple_reports(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        w = self._one_window_per_token()
        result = run_x9_6h_conservative_proof(
            self.db, self.bk, batches=[_canonical_batch(), _canonical_batch()],
            operator_approved=True,
            token_ids_per_batch=[self.tids, self.tids],
            window_ids_per_batch=[w, w],
        )
        self.assertEqual(result["lane_x9_status"], "LANE_X9_COMPLETED")
        self.assertEqual(len(result["batch_reports"]), 2)

    def test_repeated_same_tokens_across_batches_allowed(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        w = self._one_window_per_token()
        result = run_x9_6h_conservative_proof(
            self.db, self.bk, batches=[_canonical_batch()] * 3,
            operator_approved=True,
            token_ids_per_batch=[self.tids] * 3,
            window_ids_per_batch=[w, w, w],
        )
        self.assertEqual(result["lane_x9_status"], "LANE_X9_COMPLETED")
        self.assertEqual(len(result["batch_reports"]), 3)

    def test_run_summary_total_batches_matches(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        w = self._one_window_per_token()
        result = run_x9_6h_conservative_proof(
            self.db, self.bk, batches=[_canonical_batch(), _canonical_batch()],
            operator_approved=True,
            token_ids_per_batch=[self.tids, self.tids],
            window_ids_per_batch=[w, w],
        )
        self.assertEqual(result["run_summary"]["total_batches"], 2)


# ---------------------------------------------------------------------------
# 6. Requirement 3: up to 5 WINDOW_15M cycles per batch (max boundary)
# ---------------------------------------------------------------------------

class TestX9CyclesPerBatch(unittest.TestCase):
    def test_5_cycles_per_token_accepted(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import (
            validate_x9_batch_config, LANE_X9_BATCH_MAX_CYCLES,
        )
        result = validate_x9_batch_config(
            _canonical_batch(), max_cycles=LANE_X9_BATCH_MAX_CYCLES, operator_approved=True
        )
        self.assertTrue(result["valid"])

    def test_6_cycles_per_batch_rejected(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        result = validate_x9_batch_config(_canonical_batch(), max_cycles=6, operator_approved=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("max_cycles" in r for r in result["blocked_reasons"]))

    def test_1_cycle_per_batch_accepted(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        result = validate_x9_batch_config(_canonical_batch(), max_cycles=1, operator_approved=True)
        self.assertTrue(result["valid"])

    def test_zero_cycles_rejected(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        result = validate_x9_batch_config(_canonical_batch(), max_cycles=0, operator_approved=True)
        self.assertFalse(result["valid"])

    def test_5_fixture_windows_inserted_by_test_helper(self):
        """Test helper (not production code) can seed 5 rows per token."""
        db = _make_db()
        tid = _insert_token(db, _MINT_A)
        pid = _insert_pair(db, tid, _PAIR_A)
        ids = [_insert_15m_window(db, tid, pid) for _ in range(5)]
        self.assertEqual(len(ids), 5)
        conn = sqlite3.connect(str(db))
        count = conn.execute(
            "SELECT COUNT(*) FROM printer_memory_windows WHERE token_id = ? AND window_kind = 'WINDOW_15M'",
            (tid,),
        ).fetchone()[0]
        conn.close()
        self.assertEqual(count, 5)

    def test_batch_report_counts_5_fixture_windows(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        db = _make_db()
        tid = _insert_token(db, _MINT_A)
        pid = _insert_pair(db, tid, _PAIR_A)
        ids = [_insert_15m_window(db, tid, pid) for _ in range(5)]
        report = produce_x9_batch_report(
            db, 0, [tid], [_make_token_config(_MINT_A, _PAIR_A)], window_ids=ids
        )
        self.assertEqual(report["windows_attempted"], 5)


# ---------------------------------------------------------------------------
# 7. Requirement 4: 5 × 15m does NOT auto-create clean memory
# ---------------------------------------------------------------------------

class TestX9FiveCyclesNotAutoClean(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()
        self.bk = _make_backup(self.db)
        self.tid = _insert_token(self.db, _MINT_A)
        self.pid = _insert_pair(self.db, self.tid, _PAIR_A)

    def test_5_partial_outcomes_produce_zero_clean(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        ids = [_insert_15m_window(self.db, self.tid, self.pid, "PARTIAL_MEMORY") for _ in range(5)]
        report = produce_x9_batch_report(
            self.db, 0, [self.tid], [_make_token_config(_MINT_A, _PAIR_A)], window_ids=ids
        )
        self.assertEqual(report["clean_count"], 0)
        self.assertEqual(report["windows_attempted"], 5)
        self.assertEqual(report["clean_yield_rate"], 0.0)

    def test_5_dirty_outcomes_produce_zero_clean(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        ids = [_insert_15m_window(self.db, self.tid, self.pid, "DIRTY_MEMORY") for _ in range(5)]
        report = produce_x9_batch_report(
            self.db, 0, [self.tid], [_make_token_config(_MINT_A, _PAIR_A)], window_ids=ids
        )
        self.assertEqual(report["clean_count"], 0)
        self.assertEqual(report["dirty_count"], 5)

    def test_clean_requires_explicit_clean_memory_status(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        ids = [_insert_15m_window(self.db, self.tid, self.pid, "CLEAN_MEMORY")]
        ids += [_insert_15m_window(self.db, self.tid, self.pid, "PARTIAL_MEMORY") for _ in range(4)]
        report = produce_x9_batch_report(
            self.db, 0, [self.tid], [_make_token_config(_MINT_A, _PAIR_A)], window_ids=ids
        )
        self.assertEqual(report["clean_count"], 1)
        self.assertEqual(report["partial_count"], 4)
        self.assertEqual(report["windows_attempted"], 5)

    def test_5m_support_rows_not_counted_as_15m_clean(self):
        """5m rows inserted by test (simulating X8 output) must not appear in 15m counts."""
        conn = sqlite3.connect(str(self.db))
        conn.execute("PRAGMA foreign_keys = ON")
        now = "2026-07-04T10:00:00+00:00"
        for _ in range(5):
            conn.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, closed_at,
                    memory_status, data_quality_label, do_not_train,
                    window_status, memory_quality_label,
                    supporting_context_json, created_by_phase, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (self.tid, self.pid, "WINDOW_5M_MICRO_EVENT", now, now,
                 "CLEAN_MEMORY", "CLEAN_DATA", 0,
                 "WINDOW_CLOSED", "CLEAN_MEMORY",
                 json.dumps({"created_by": "test_x8_sim"}), "test", now, now),
            )
        conn.commit()
        conn.close()
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        report = produce_x9_batch_report(
            self.db, 0, [self.tid], [_make_token_config(_MINT_A, _PAIR_A)]
        )
        self.assertEqual(report["clean_count"], 0,
                         "5m CLEAN_MEMORY rows must not count as 15m clean memories")


# ---------------------------------------------------------------------------
# 8. Requirement 5: zero-clean batch is valid
# ---------------------------------------------------------------------------

class TestX9ZeroCleanBatchValid(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()
        self.bk = _make_backup(self.db)
        self.tid_a, self.pid_a, self.tid_b, self.pid_b, self.tid_c, self.pid_c = (
            _seed_abc(self.db)
        )

    def test_zero_clean_batch_not_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        wid_a = _insert_15m_window(self.db, self.tid_a, self.pid_a, "DIRTY_MEMORY")
        wid_b = _insert_15m_window(self.db, self.tid_b, self.pid_b, "DIRTY_MEMORY")
        wid_c = _insert_15m_window(self.db, self.tid_c, self.pid_c, "DIRTY_MEMORY")
        result = run_x9_6h_conservative_proof(
            self.db, self.bk, batches=[_canonical_batch()],
            operator_approved=True,
            token_ids_per_batch=[[self.tid_a, self.tid_b, self.tid_c]],
            window_ids_per_batch=[[wid_a, wid_b, wid_c]],
        )
        self.assertEqual(result["lane_x9_status"], "LANE_X9_COMPLETED")
        self.assertEqual(result["batch_reports"][0]["clean_count"], 0)
        self.assertTrue(result["batch_reports"][0]["zero_clean_is_valid"])

    def test_zero_clean_run_valid_flag_in_summary(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        reports = [{"windows_attempted": 5, "clean_count": 0, "dirty_count": 5,
                    "audit_only_count": 0, "partial_count": 0, "token_mints": [_MINT_A]}]
        summary = produce_x9_run_summary(reports)
        self.assertTrue(summary["zero_clean_run_is_valid"])
        self.assertEqual(summary["total_clean"], 0)
        self.assertEqual(summary["clean_yield_per_run"], 0.0)

    def test_zero_clean_all_batches_not_error(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        reports = [
            {"windows_attempted": 5, "clean_count": 0, "dirty_count": 5,
             "audit_only_count": 0, "partial_count": 0, "token_mints": [_MINT_A]},
            {"windows_attempted": 5, "clean_count": 0, "dirty_count": 3,
             "audit_only_count": 2, "partial_count": 0, "token_mints": [_MINT_B]},
        ]
        summary = produce_x9_run_summary(reports)
        self.assertTrue(summary["zero_clean_run_is_valid"])
        self.assertEqual(summary["total_clean"], 0)


# ---------------------------------------------------------------------------
# 9. Requirement 6: WINDOW_15M main-only
# ---------------------------------------------------------------------------

class TestX9Window15MMainOnly(unittest.TestCase):
    def test_disabled_window_kinds_defined(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _DISABLED_WINDOWS
        for kind in ("WINDOW_1H", "WINDOW_4H", "WINDOW_12H", "WINDOW_24H"):
            self.assertIn(kind, _DISABLED_WINDOWS)

    def test_1h_window_kind_in_token_config_rejected(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        batch = [
            {"token_mint": _MINT_A, "pair_address": _PAIR_A,
             "chain": "solana", "operator_approved": True, "window_kind": "WINDOW_1H"},
            _make_token_config(_MINT_B, _PAIR_B),
            _make_token_config(_MINT_C, _PAIR_C),
        ]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("WINDOW_1H" in r for r in result["blocked_reasons"]))

    def test_4h_window_kind_rejected(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        batch = [
            {"token_mint": _MINT_A, "pair_address": _PAIR_A,
             "chain": "solana", "operator_approved": True, "window_kind": "WINDOW_4H"},
            _make_token_config(_MINT_B, _PAIR_B),
            _make_token_config(_MINT_C, _PAIR_C),
        ]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertFalse(result["valid"])

    def test_batch_report_only_reads_15m_rows(self):
        """Report must not count 5m or 1h rows even if they exist for the token."""
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        db = _make_db()
        tid = _insert_token(db, _MINT_A)
        pid = _insert_pair(db, tid, _PAIR_A)
        wid = _insert_15m_window(db, tid, pid, "CLEAN_MEMORY")
        # also insert a 5m row — should be excluded
        conn = sqlite3.connect(str(db))
        conn.execute("PRAGMA foreign_keys = ON")
        now = "2026-07-04T10:00:00+00:00"
        conn.execute(
            """INSERT INTO printer_memory_windows
               (token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tid, pid, "WINDOW_5M_MICRO_EVENT", now, now,
             "CLEAN_MEMORY", "CLEAN_DATA", 0, "WINDOW_CLOSED", "CLEAN_MEMORY",
             json.dumps({"created_by": "test"}), "test", now, now),
        )
        conn.commit()
        conn.close()
        report = produce_x9_batch_report(
            db, 0, [tid], [_make_token_config(_MINT_A, _PAIR_A)], window_ids=[wid]
        )
        self.assertEqual(report["clean_count"], 1)
        self.assertEqual(report["windows_attempted"], 1)


# ---------------------------------------------------------------------------
# 10. Requirement 7: 5m support-only
# ---------------------------------------------------------------------------

class TestX9FiveMSupportOnly(unittest.TestCase):
    def test_5m_as_main_window_rejected_in_batch_config(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        batch = [
            {"token_mint": _MINT_A, "pair_address": _PAIR_A,
             "chain": "solana", "operator_approved": True,
             "window_kind": "WINDOW_5M_MICRO_EVENT"},
            _make_token_config(_MINT_B, _PAIR_B),
            _make_token_config(_MINT_C, _PAIR_C),
        ]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("support-only" in r for r in result["blocked_reasons"]))

    def test_support_only_windows_defined(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _SUPPORT_ONLY_WINDOWS
        self.assertIn("WINDOW_5M_MICRO_EVENT", _SUPPORT_ONLY_WINDOWS)

    def test_no_synthetic_writer_in_production_module(self):
        import printer_v1.operator_cli.lane_x9_6h_conservative_run as m
        self.assertFalse(hasattr(m, "record_x9_batch_windows"),
                         "record_x9_batch_windows must not exist in production module")

    def test_5m_support_flag_in_batch_report(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        db = _make_db()
        tid = _insert_token(db, _MINT_A)
        report = produce_x9_batch_report(
            db, 0, [tid], [_make_token_config(_MINT_A, _PAIR_A)]
        )
        self.assertTrue(report["5m_support_only"])

    def test_5m_support_flag_in_run_summary(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        summary = produce_x9_run_summary(
            [{"windows_attempted": 1, "clean_count": 0, "dirty_count": 1,
              "audit_only_count": 0, "partial_count": 0, "token_mints": [_MINT_A]}]
        )
        self.assertTrue(summary["5m_support_only"])


# ---------------------------------------------------------------------------
# 11. Requirement 8: no silent replacement
# ---------------------------------------------------------------------------

class TestX9NoSilentReplacement(unittest.TestCase):
    def test_batch_without_operator_approval_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        result = validate_x9_batch_config(_canonical_batch(), operator_approved=False)
        self.assertFalse(result["valid"])
        self.assertTrue(any("operator_approved" in r for r in result["blocked_reasons"]))

    def test_run_without_operator_approval_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        db = _make_db()
        bk = _make_backup(db)
        result = run_x9_6h_conservative_proof(
            db, bk, batches=[_canonical_batch()], operator_approved=False
        )
        self.assertEqual(result["lane_x9_status"], "LANE_X9_BLOCKED")
        self.assertTrue(any("operator_approved" in r for r in result["blocked_reasons"]))

    def test_token_without_operator_approved_flag_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        batch = [
            {"token_mint": _MINT_A, "pair_address": _PAIR_A,
             "chain": "solana", "operator_approved": False},
            _make_token_config(_MINT_B, _PAIR_B),
            _make_token_config(_MINT_C, _PAIR_C),
        ]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("operator_approved" in r for r in result["blocked_reasons"]))

    def test_no_silent_replacement_flag_in_batch_report(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_batch_report
        db = _make_db()
        tid = _insert_token(db, _MINT_A)
        report = produce_x9_batch_report(db, 0, [tid], [_make_token_config(_MINT_A, _PAIR_A)])
        self.assertTrue(report["no_silent_replacement"])

    def test_no_silent_replacement_flag_in_run_summary(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        summary = produce_x9_run_summary(
            [{"windows_attempted": 0, "clean_count": 0, "dirty_count": 0,
              "audit_only_count": 0, "partial_count": 0, "token_mints": []}]
        )
        self.assertTrue(summary["no_silent_replacement"])

    def test_duplicate_mints_in_same_batch_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        batch = [
            _make_token_config(_MINT_A, _PAIR_A),
            _make_token_config(_MINT_A, _PAIR_B),
            _make_token_config(_MINT_C, _PAIR_C),
        ]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("duplicate" in r.lower() for r in result["blocked_reasons"]))


# ---------------------------------------------------------------------------
# 12. Requirement 9: no retrieval / paper / BUY / position / PnL unlock
# ---------------------------------------------------------------------------

class TestX9NoUnlocks(unittest.TestCase):
    def _blocked_result(self) -> dict[str, Any]:
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        db = _make_db()
        bk = _make_backup(db)
        return run_x9_6h_conservative_proof(db, bk, batches=None, operator_approved=False)

    def test_no_retrieval_in_result(self):
        self.assertTrue(self._blocked_result().get("no_retrieval"))

    def test_no_paper_decisions_in_result(self):
        self.assertTrue(self._blocked_result().get("no_paper_decisions"))

    def test_no_buy_sell_hold_in_result(self):
        self.assertTrue(self._blocked_result().get("no_buy_sell_hold"))

    def test_no_positions_pnl_in_result(self):
        self.assertTrue(self._blocked_result().get("no_positions_pnl"))

    def test_no_1h_4h_12h_24h_in_result(self):
        self.assertTrue(self._blocked_result().get("no_1h_4h_12h_24h"))

    def test_forbidden_tables_defined(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import _FORBIDDEN_WRITE_TABLES
        for tbl in ("printer_paper_decisions", "printer_paper_positions",
                    "printer_retrieval_candidates", "printer_memories"):
            self.assertIn(tbl, _FORBIDDEN_WRITE_TABLES)

    def test_produce_batch_report_writes_no_forbidden_tables(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import (
            produce_x9_batch_report, _FORBIDDEN_WRITE_TABLES,
        )
        db = _make_db()
        tid = _insert_token(db, _MINT_A)
        pid = _insert_pair(db, tid, _PAIR_A)
        _insert_15m_window(db, tid, pid)
        produce_x9_batch_report(db, 0, [tid], [_make_token_config(_MINT_A, _PAIR_A)])
        conn = sqlite3.connect(str(db))
        for table in _FORBIDDEN_WRITE_TABLES:
            try:
                count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                self.assertEqual(count, 0, f"Forbidden table {table!r} has rows")
            except sqlite3.OperationalError:
                pass
        conn.close()


# ---------------------------------------------------------------------------
# 13. Gate checks — missing db / backup
# ---------------------------------------------------------------------------

class TestX9GateChecks(unittest.TestCase):
    def test_missing_db_path_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        result = run_x9_6h_conservative_proof(
            "/nonexistent/db.db", "/tmp/bk.db",
            batches=[_canonical_batch()], operator_approved=True,
        )
        self.assertEqual(result["lane_x9_status"], "LANE_X9_BLOCKED")
        self.assertTrue(any("db_path" in r for r in result["blocked_reasons"]))

    def test_missing_backup_proof_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        db = _make_db()
        result = run_x9_6h_conservative_proof(
            db, "/nonexistent/backup.db",
            batches=[_canonical_batch()], operator_approved=True,
        )
        self.assertEqual(result["lane_x9_status"], "LANE_X9_BLOCKED")
        self.assertTrue(any("backup_proof_path" in r for r in result["blocked_reasons"]))

    def test_none_db_path_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        result = run_x9_6h_conservative_proof(None, None, batches=None, operator_approved=True)
        self.assertEqual(result["lane_x9_status"], "LANE_X9_BLOCKED")

    def test_empty_batches_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        db = _make_db()
        bk = _make_backup(db)
        result = run_x9_6h_conservative_proof(db, bk, batches=[], operator_approved=True)
        self.assertEqual(result["lane_x9_status"], "LANE_X9_BLOCKED")

    def test_none_batches_blocked(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        db = _make_db()
        bk = _make_backup(db)
        result = run_x9_6h_conservative_proof(db, bk, batches=None, operator_approved=True)
        self.assertEqual(result["lane_x9_status"], "LANE_X9_BLOCKED")


# ---------------------------------------------------------------------------
# 14. Batch size boundary checks
# ---------------------------------------------------------------------------

class TestX9BatchSizeBoundaries(unittest.TestCase):
    def test_2_tokens_rejected(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        batch = [_make_token_config(_MINT_A, _PAIR_A), _make_token_config(_MINT_B, _PAIR_B)]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertFalse(result["valid"])
        self.assertTrue(any("minimum" in r for r in result["blocked_reasons"]))

    def test_6_tokens_rejected(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        mints = [f"X9Mint6{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" for i in range(6)]
        pairs = [f"X9Pair6{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" for i in range(6)]
        batch = [_make_token_config(m, p) for m, p in zip(mints, pairs)]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertFalse(result["valid"])
        self.assertTrue(
            any("maximum" in r or "no_10_token_expansion" in r for r in result["blocked_reasons"])
        )

    def test_3_tokens_valid(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        result = validate_x9_batch_config(_canonical_batch(), operator_approved=True)
        self.assertTrue(result["valid"])

    def test_4_tokens_valid(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import validate_x9_batch_config
        mints = [f"X9Mint4{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" for i in range(4)]
        pairs = [f"X9Pair4{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" for i in range(4)]
        batch = [_make_token_config(m, p) for m, p in zip(mints, pairs)]
        result = validate_x9_batch_config(batch, operator_approved=True)
        self.assertTrue(result["valid"])


# ---------------------------------------------------------------------------
# 15. Run summary calculations
# ---------------------------------------------------------------------------

class TestX9RunSummary(unittest.TestCase):
    def test_yield_per_hour_computed(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        reports = [{"windows_attempted": 5, "clean_count": 3, "dirty_count": 1,
                    "audit_only_count": 0, "partial_count": 1, "token_mints": [_MINT_A]}]
        summary = produce_x9_run_summary(reports)
        self.assertGreater(summary["clean_yield_per_hour"], 0.0)
        self.assertAlmostEqual(summary["clean_yield_per_run"], 3/5, places=3)

    def test_empty_batches_yield_zero(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        summary = produce_x9_run_summary([])
        self.assertEqual(summary["total_batches"], 0)
        self.assertEqual(summary["clean_yield_per_run"], 0.0)
        self.assertEqual(summary["clean_yield_per_hour"], 0.0)

    def test_unique_token_mints_deduped_across_batches(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        reports = [
            {"windows_attempted": 2, "clean_count": 1, "dirty_count": 1,
             "audit_only_count": 0, "partial_count": 0, "token_mints": [_MINT_A, _MINT_B]},
            {"windows_attempted": 2, "clean_count": 1, "dirty_count": 1,
             "audit_only_count": 0, "partial_count": 0, "token_mints": [_MINT_A, _MINT_C]},
        ]
        summary = produce_x9_run_summary(reports)
        self.assertEqual(sorted(summary["unique_token_mints"]),
                         sorted([_MINT_A, _MINT_B, _MINT_C]))
        self.assertEqual(summary["total_tokens_tracked"], 3)

    def test_all_locks_preserved_flag(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import produce_x9_run_summary
        summary = produce_x9_run_summary(
            [{"windows_attempted": 0, "clean_count": 0, "dirty_count": 0,
              "audit_only_count": 0, "partial_count": 0, "token_mints": []}]
        )
        self.assertTrue(summary["all_locks_preserved"])


# ---------------------------------------------------------------------------
# 16. Run result structure completeness
# ---------------------------------------------------------------------------

class TestX9ResultStructure(unittest.TestCase):
    def setUp(self):
        self.db = _make_db()
        self.bk = _make_backup(self.db)
        self.tid_a, self.pid_a, self.tid_b, self.pid_b, self.tid_c, self.pid_c = (
            _seed_abc(self.db)
        )

    def _run(self) -> dict[str, Any]:
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import run_x9_6h_conservative_proof
        # seed: token_a gets CLEAN+PARTIAL, token_b gets DIRTY+AUDIT_ONLY, token_c gets PARTIAL
        ids_a = [
            _insert_15m_window(self.db, self.tid_a, self.pid_a, "CLEAN_MEMORY"),
            _insert_15m_window(self.db, self.tid_a, self.pid_a, "PARTIAL_MEMORY"),
        ]
        ids_b = [
            _insert_15m_window(self.db, self.tid_b, self.pid_b, "DIRTY_MEMORY"),
            _insert_15m_window(self.db, self.tid_b, self.pid_b, "AUDIT_ONLY"),
        ]
        ids_c = [
            _insert_15m_window(self.db, self.tid_c, self.pid_c, "PARTIAL_MEMORY"),
        ]
        all_ids = ids_a + ids_b + ids_c
        return run_x9_6h_conservative_proof(
            self.db, self.bk, batches=[_canonical_batch()],
            operator_approved=True,
            token_ids_per_batch=[[self.tid_a, self.tid_b, self.tid_c]],
            window_ids_per_batch=[all_ids],
        )

    def test_completed_status(self):
        self.assertEqual(self._run()["lane_x9_status"], "LANE_X9_COMPLETED")

    def test_hard_locks_present_in_result(self):
        result = self._run()
        self.assertIn("hard_locks", result)
        self.assertEqual(len(result["hard_locks"]), 26)

    def test_batch_reports_list_present(self):
        result = self._run()
        self.assertIsInstance(result["batch_reports"], list)
        self.assertEqual(len(result["batch_reports"]), 1)

    def test_run_summary_present(self):
        self.assertIsNotNone(self._run()["run_summary"])

    def test_batch_report_fields(self):
        rpt = self._run()["batch_reports"][0]
        for key in ("windows_attempted", "clean_count", "dirty_count",
                    "audit_only_count", "partial_count",
                    "clean_yield_rate", "zero_clean_is_valid",
                    "15m_main_only", "5m_support_only", "no_silent_replacement"):
            self.assertIn(key, rpt, f"missing key {key!r}")

    def test_run_summary_fields(self):
        smry = self._run()["run_summary"]
        for key in ("total_batches", "total_clean", "total_dirty",
                    "clean_yield_per_run", "clean_yield_per_hour",
                    "outer_bound_enforced", "zero_clean_run_is_valid",
                    "15m_main_only", "5m_support_only", "no_silent_replacement",
                    "all_locks_preserved"):
            self.assertIn(key, smry, f"run_summary missing key {key!r}")

    def test_clean_count_correct_in_batch_report(self):
        rpt = self._run()["batch_reports"][0]
        self.assertEqual(rpt["clean_count"], 1)
        self.assertEqual(rpt["partial_count"], 2)
        self.assertEqual(rpt["dirty_count"], 1)
        self.assertEqual(rpt["audit_only_count"], 1)
        self.assertEqual(rpt["windows_attempted"], 5)

    def test_command_name_in_result(self):
        self.assertEqual(self._run()["command"], "printer-run-lane-x9-6h-conservative")


# ---------------------------------------------------------------------------
# 17. Module-level identity
# ---------------------------------------------------------------------------

class TestX9ModuleIdentity(unittest.TestCase):
    def test_command_name_constant(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import LANE_X9_COMMAND_NAME
        self.assertEqual(LANE_X9_COMMAND_NAME, "printer-run-lane-x9-6h-conservative")

    def test_status_constants_defined(self):
        from printer_v1.operator_cli.lane_x9_6h_conservative_run import (
            LANE_X9_STATUS_COMPLETED, LANE_X9_STATUS_BLOCKED, LANE_X9_STATUS_STOPPED,
        )
        self.assertEqual(LANE_X9_STATUS_COMPLETED, "LANE_X9_COMPLETED")
        self.assertEqual(LANE_X9_STATUS_BLOCKED, "LANE_X9_BLOCKED")
        self.assertEqual(LANE_X9_STATUS_STOPPED, "LANE_X9_STOPPED")

    def test_cli_entry_importable(self):
        from printer_v1.operator_cli.commands import main_run_lane_x9_6h_conservative
        self.assertTrue(callable(main_run_lane_x9_6h_conservative))


if __name__ == "__main__":
    unittest.main()
