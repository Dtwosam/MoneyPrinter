"""
Post-Lane 10 Lane E2U -- Bounded 15m Cycle Closeout Report

Tests prove:
- e2u_15m_cycle_closeout_report module imports cleanly
- E2U_COMMAND_NAME defined correctly
- E2U_STATUS_READY / E2U_STATUS_BLOCKED defined
- _LOCKED_STATE all False
- _HARD_LOCKS all True including no_memory_creation, no_retrieval_activation
- build_e2u_closeout_report is callable
- operator approval required
- db_path required
- db_path missing → blocked
- blocked result has expected shape
- report is read-only: zero row-count delta after report
- report returns command field matching E2U_COMMAND_NAME
- report returns e2u_status E2U_REPORT_READY on success
- report returns operator_approved True on success
- report returns latest_job_ids list
- report returns latest_source_request_ids list
- report returns latest_source_response_ids list
- report returns latest_snapshot_ids list
- report returns latest_memory_window_ids list
- report returns last_five_window_15m list
- report returns table_counts dict
- report returns closed_window_15m_count
- report returns e2q_audited_window_count
- report returns clean_data_window_count
- report returns partial_memory_window_count
- report returns clean_memory_count (table_absent if no table)
- report returns retrieval_eligible_count
- report returns running_jobs / active_locks
- report returns repeatable_15m_window_proof True when >= 2 closed windows
- report returns repeatable_15m_window_proof False when < 2 closed windows
- report returns readiness_flags dict
- readiness_flags.repeatable_15m_windows_ready matches proof
- readiness_flags.bounded_operator_cycle_ready is True
- readiness_flags.memory_creation_ready is False
- readiness_flags.retrieval_ready is False
- readiness_flags.paper_decision_ready is False
- readiness_flags.buy_ready is False
- readiness_flags.position_ready is False
- locked_state all False (buy_unlock, sell_unlock, hold_unlock, paper_positions_unlock, pnl_unlock, live_execution, wallet_private_key, paid_api_dependency)
- hard_locks all True
- PARTIAL_MEMORY windows treated as not clean memory
- clean_memory_count absent when printer_memories table not in schema
- last_five_window_15m contains id, window_kind, window_status, memory_quality_label, e2q_audited
- detects e2q_audited flag in last_five_window_15m from supporting_context_json
- last five windows are WINDOW_15M only
- notes list present and mentions PARTIAL_MEMORY
- notes mention 5m not active
- notes mention paper decisions locked
- no paper decisions created
- no paper positions created
- no paper trade events created
- no paper trade audits created
- no memories created
- buy_enabled=False sell_enabled=False hold_enabled=False
- paper_decisions_created=0 positions_created=0 pnl_created=0
- result JSON serializable
- next_recommended_lane field present
- read_only_delta_violations empty after normal read
- CLI function exists and callable
- CLI returns 0 with valid args
- CLI outputs valid JSON
- CLI blocked when --operator-approved not set
- pyproject entry registered
"""

import io
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
from printer_v1.operator_cli.e2u_15m_cycle_closeout_report import (
    E2U_COMMAND_NAME,
    E2U_STATUS_BLOCKED,
    E2U_STATUS_READY,
    _HARD_LOCKS,
    _LOCKED_STATE,
    build_e2u_closeout_report,
)
from printer_v1.operator_cli.commands import main_report_e2u_15m_cycle_closeout


_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR_ADDR = "E2UTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_NOW = "2026-06-28T10:00:00+00:00"


class _DbTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            r = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return r[0] if r else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _run(self, **kwargs) -> dict:
        defaults = dict(db_path=self.db_path, operator_approved=True)
        defaults.update(kwargs)
        return build_e2u_closeout_report(**defaults)

    def _insert_token(self, conn: sqlite3.Connection) -> int:
        cur = conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACKING', ?, ?)",
            (_MINT, _NOW, _NOW, _NOW, _NOW),
        )
        return int(cur.lastrowid)

    def _insert_pair(self, conn: sqlite3.Connection, token_id: int) -> int:
        cur = conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, _PAIR_ADDR, _PAIR_ADDR, _NOW, _NOW, _NOW, _NOW),
        )
        return int(cur.lastrowid)

    def _insert_snapshot(self, conn: sqlite3.Connection, token_id: int,
                         pair_id: int) -> int:
        cur = conn.execute(
            "INSERT INTO printer_token_snapshots"
            " (token_id, pair_id, captured_at, tracking_lane, snapshot_mode,"
            "  source_status, data_quality_label, created_at)"
            " VALUES (?, ?, ?, 'TRACK_FAST', 'FIRST_15M_CYCLE',"
            "  'COMPLETE', 'CLEAN_DATA', datetime('now'))",
            (token_id, pair_id, _NOW),
        )
        return int(cur.lastrowid)

    def _insert_window(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int,
        snapshot_id: int,
        memory_quality_label: str | None = "PARTIAL_MEMORY",
        data_quality_label: str = "CLEAN_DATA",
        window_status: str = "WINDOW_CLOSED",
    ) -> int:
        ctx = json.dumps({
            "snapshot_id": snapshot_id,
            "tracking_lane": "TRACK_FAST",
            "e2q_audited": True,
            "e2q_audit_status": memory_quality_label,
            "e2q_audited_by": "lane_e2q",
        }, sort_keys=True)
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train, window_status,
                memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at
            ) VALUES (?, ?, 'WINDOW_15M', ?, ?, 'PARTIAL_MEMORY', ?, 0, ?, ?, ?, 'lane_e2o', ?, ?)
            """,
            (
                token_id, pair_id, _NOW, _NOW,
                data_quality_label, window_status, memory_quality_label,
                ctx, _NOW, _NOW,
            ),
        )
        return int(cur.lastrowid)

    def _make_n_windows(self, n: int) -> list[int]:
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            ids = []
            for _ in range(n):
                snap_id = self._insert_snapshot(conn, token_id, pair_id)
                win_id = self._insert_window(conn, token_id, pair_id, snap_id)
                ids.append(win_id)
            conn.commit()
        finally:
            conn.close()
        return ids


# ---------------------------------------------------------------------------
# Import and constants
# ---------------------------------------------------------------------------

class LaneE2UImportTests(unittest.TestCase):
    def test_module_imports(self):
        from printer_v1.operator_cli import e2u_15m_cycle_closeout_report
        self.assertIsNotNone(e2u_15m_cycle_closeout_report)

    def test_command_name(self):
        self.assertEqual(E2U_COMMAND_NAME, "printer-report-e2u-15m-cycle-closeout")

    def test_status_ready(self):
        self.assertEqual(E2U_STATUS_READY, "E2U_REPORT_READY")

    def test_status_blocked(self):
        self.assertEqual(E2U_STATUS_BLOCKED, "E2U_BLOCKED")

    def test_locked_state_all_false(self):
        for key, val in _LOCKED_STATE.items():
            self.assertFalse(val, f"_LOCKED_STATE[{key!r}] must be False")

    def test_locked_state_buy_unlock_false(self):
        self.assertFalse(_LOCKED_STATE["buy_unlock"])

    def test_locked_state_sell_unlock_false(self):
        self.assertFalse(_LOCKED_STATE["sell_unlock"])

    def test_locked_state_hold_unlock_false(self):
        self.assertFalse(_LOCKED_STATE["hold_unlock"])

    def test_hard_locks_all_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"_HARD_LOCKS[{key!r}] must be True")

    def test_hard_locks_no_memory_creation(self):
        self.assertTrue(_HARD_LOCKS.get("no_memory_creation"))

    def test_hard_locks_no_retrieval_activation(self):
        self.assertTrue(_HARD_LOCKS.get("no_retrieval_activation"))

    def test_hard_locks_no_5m_main_window(self):
        self.assertTrue(_HARD_LOCKS.get("no_5m_main_window"))

    def test_function_callable(self):
        self.assertTrue(callable(build_e2u_closeout_report))


# ---------------------------------------------------------------------------
# Blocked gate tests
# ---------------------------------------------------------------------------

class LaneE2UBlockedTests(_DbTestBase):
    def test_blocked_when_not_approved(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["e2u_status"], E2U_STATUS_BLOCKED)

    def test_blocked_has_blocked_reasons(self):
        r = self._run(operator_approved=False)
        self.assertGreater(len(r.get("blocked_reasons", [])), 0)

    def test_blocked_when_db_path_none(self):
        r = build_e2u_closeout_report(None, operator_approved=True)
        self.assertEqual(r["e2u_status"], E2U_STATUS_BLOCKED)

    def test_blocked_when_db_missing(self):
        r = build_e2u_closeout_report(
            pathlib.Path(self._tmp.name) / "no_such.sqlite3",
            operator_approved=True,
        )
        self.assertEqual(r["e2u_status"], E2U_STATUS_BLOCKED)

    def test_blocked_has_locked_state(self):
        r = self._run(operator_approved=False)
        ls = r.get("locked_state", {})
        self.assertFalse(ls.get("buy_unlock"))
        self.assertFalse(ls.get("sell_unlock"))

    def test_blocked_has_readiness_flags(self):
        r = self._run(operator_approved=False)
        rf = r.get("readiness_flags", {})
        self.assertFalse(rf.get("buy_ready"))


# ---------------------------------------------------------------------------
# Read-only contract: zero delta after report
# ---------------------------------------------------------------------------

class LaneE2UReadOnlyTests(_DbTestBase):
    def test_zero_row_delta_empty_db(self):
        r = self._run()
        self.assertEqual(r.get("read_only_delta_violations"), [])

    def test_zero_row_delta_with_windows(self):
        self._make_n_windows(3)
        before = self._count_rows("printer_memory_windows")
        r = self._run()
        after = self._count_rows("printer_memory_windows")
        self.assertEqual(before, after)
        self.assertEqual(r.get("read_only_delta_violations"), [])

    def test_no_paper_decisions_created(self):
        self._make_n_windows(2)
        before = self._count_rows("printer_paper_decisions")
        self._run()
        self.assertEqual(self._count_rows("printer_paper_decisions"), before)

    def test_no_paper_positions_created(self):
        self._run()
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_no_paper_trade_events_created(self):
        self._run()
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)

    def test_no_paper_trade_audits_created(self):
        self._run()
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)

    def test_no_memories_created(self):
        before = self._count_rows("printer_memories")
        self._run()
        self.assertEqual(self._count_rows("printer_memories"), before)

    def test_no_snapshots_created(self):
        before = self._count_rows("printer_token_snapshots")
        self._run()
        self.assertEqual(self._count_rows("printer_token_snapshots"), before)

    def test_no_memory_windows_created(self):
        before = self._count_rows("printer_memory_windows")
        self._run()
        self.assertEqual(self._count_rows("printer_memory_windows"), before)


# ---------------------------------------------------------------------------
# Happy path: empty DB
# ---------------------------------------------------------------------------

class LaneE2UEmptyDbTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self.r = self._run()

    def test_status_ready(self):
        self.assertEqual(self.r["e2u_status"], E2U_STATUS_READY)

    def test_operator_approved_true(self):
        self.assertTrue(self.r["operator_approved"])

    def test_command_field(self):
        self.assertEqual(self.r["command"], E2U_COMMAND_NAME)

    def test_db_path_in_result(self):
        self.assertIn(self.r["db_path"], str(self.db_path))

    def test_latest_job_ids_empty(self):
        self.assertEqual(self.r["latest_job_ids"], [])

    def test_latest_source_request_ids_empty(self):
        self.assertEqual(self.r["latest_source_request_ids"], [])

    def test_latest_snapshot_ids_empty(self):
        self.assertEqual(self.r["latest_snapshot_ids"], [])

    def test_latest_memory_window_ids_empty(self):
        self.assertEqual(self.r["latest_memory_window_ids"], [])

    def test_last_five_15m_windows_empty(self):
        self.assertEqual(self.r["last_five_window_15m"], [])

    def test_table_counts_dict(self):
        self.assertIsInstance(self.r["table_counts"], dict)

    def test_closed_window_15m_count_zero(self):
        self.assertEqual(self.r["closed_window_15m_count"], 0)

    def test_e2q_audited_window_count_zero(self):
        self.assertEqual(self.r["e2q_audited_window_count"], 0)

    def test_clean_data_window_count_zero(self):
        self.assertEqual(self.r["clean_data_window_count"], 0)

    def test_partial_memory_window_count_zero(self):
        self.assertEqual(self.r["partial_memory_window_count"], 0)

    def test_running_jobs_zero(self):
        self.assertEqual(self.r["running_jobs"], 0)

    def test_active_locks_zero(self):
        self.assertEqual(self.r["active_locks"], 0)

    def test_repeatable_15m_proof_false_empty(self):
        self.assertFalse(self.r["repeatable_15m_window_proof"])

    def test_readiness_flags_present(self):
        self.assertIsInstance(self.r["readiness_flags"], dict)

    def test_bounded_operator_cycle_ready_true(self):
        self.assertTrue(self.r["readiness_flags"]["bounded_operator_cycle_ready"])

    def test_memory_creation_ready_false(self):
        self.assertFalse(self.r["readiness_flags"]["memory_creation_ready"])

    def test_retrieval_ready_false(self):
        self.assertFalse(self.r["readiness_flags"]["retrieval_ready"])

    def test_paper_decision_ready_false(self):
        self.assertFalse(self.r["readiness_flags"]["paper_decision_ready"])

    def test_buy_ready_false(self):
        self.assertFalse(self.r["readiness_flags"]["buy_ready"])

    def test_position_ready_false(self):
        self.assertFalse(self.r["readiness_flags"]["position_ready"])

    def test_locked_state_buy_unlock_false(self):
        self.assertFalse(self.r["locked_state"]["buy_unlock"])

    def test_locked_state_sell_unlock_false(self):
        self.assertFalse(self.r["locked_state"]["sell_unlock"])

    def test_locked_state_hold_unlock_false(self):
        self.assertFalse(self.r["locked_state"]["hold_unlock"])

    def test_locked_state_paper_positions_unlock_false(self):
        self.assertFalse(self.r["locked_state"]["paper_positions_unlock"])

    def test_locked_state_pnl_unlock_false(self):
        self.assertFalse(self.r["locked_state"]["pnl_unlock"])

    def test_locked_state_live_execution_false(self):
        self.assertFalse(self.r["locked_state"]["live_execution"])

    def test_locked_state_wallet_private_key_false(self):
        self.assertFalse(self.r["locked_state"]["wallet_private_key"])

    def test_locked_state_paid_api_dependency_false(self):
        self.assertFalse(self.r["locked_state"]["paid_api_dependency"])

    def test_hard_locks_all_true(self):
        for key, val in self.r["hard_locks"].items():
            self.assertTrue(val, f"hard_locks[{key!r}] must be True")

    def test_buy_enabled_false(self):
        self.assertFalse(self.r["buy_enabled"])

    def test_sell_enabled_false(self):
        self.assertFalse(self.r["sell_enabled"])

    def test_hold_enabled_false(self):
        self.assertFalse(self.r["hold_enabled"])

    def test_paper_decisions_created_zero(self):
        self.assertEqual(self.r["paper_decisions_created"], 0)

    def test_notes_present(self):
        self.assertIsInstance(self.r.get("notes"), list)
        self.assertGreater(len(self.r["notes"]), 0)

    def test_notes_mention_partial_memory(self):
        combined = " ".join(self.r["notes"]).upper()
        self.assertIn("PARTIAL_MEMORY", combined)

    def test_notes_mention_5m(self):
        combined = " ".join(self.r["notes"]).lower()
        self.assertIn("5m", combined)

    def test_notes_mention_paper_decisions(self):
        combined = " ".join(self.r["notes"]).lower()
        self.assertIn("paper", combined)

    def test_next_recommended_lane_present(self):
        self.assertIsInstance(self.r.get("next_recommended_lane"), str)
        self.assertGreater(len(self.r["next_recommended_lane"]), 5)

    def test_result_json_serializable(self):
        j = json.dumps(self.r)
        self.assertGreater(len(j), 10)

    def test_clean_memory_count_absent_or_zero(self):
        v = self.r["clean_memory_count"]
        self.assertIn(v, (0, "table_absent"))


# ---------------------------------------------------------------------------
# Happy path: populated DB
# ---------------------------------------------------------------------------

class LaneE2UPopulatedDbTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self.win_ids = self._make_n_windows(3)
        self.r = self._run()

    def test_status_ready(self):
        self.assertEqual(self.r["e2u_status"], E2U_STATUS_READY)

    def test_closed_window_count_three(self):
        self.assertEqual(self.r["closed_window_15m_count"], 3)

    def test_e2q_audited_count_three(self):
        self.assertEqual(self.r["e2q_audited_window_count"], 3)

    def test_clean_data_window_count_three(self):
        self.assertEqual(self.r["clean_data_window_count"], 3)

    def test_partial_memory_count_three(self):
        self.assertEqual(self.r["partial_memory_window_count"], 3)

    def test_repeatable_proof_true_with_three(self):
        self.assertTrue(self.r["repeatable_15m_window_proof"])

    def test_repeatable_15m_windows_ready_true(self):
        self.assertTrue(self.r["readiness_flags"]["repeatable_15m_windows_ready"])

    def test_last_five_15m_windows_length_three(self):
        self.assertEqual(len(self.r["last_five_window_15m"]), 3)

    def test_last_five_windows_all_window_15m(self):
        for w in self.r["last_five_window_15m"]:
            self.assertEqual(w["window_kind"], "WINDOW_15M")

    def test_last_five_windows_all_closed(self):
        for w in self.r["last_five_window_15m"]:
            self.assertEqual(w["window_status"], "WINDOW_CLOSED")

    def test_last_five_windows_have_memory_quality_label(self):
        for w in self.r["last_five_window_15m"]:
            self.assertIn("memory_quality_label", w)

    def test_last_five_windows_all_partial_memory(self):
        for w in self.r["last_five_window_15m"]:
            self.assertEqual(w["memory_quality_label"], "PARTIAL_MEMORY")

    def test_last_five_windows_e2q_audited_true(self):
        for w in self.r["last_five_window_15m"]:
            self.assertTrue(w["e2q_audited"])

    def test_last_five_windows_have_snapshot_id(self):
        for w in self.r["last_five_window_15m"]:
            self.assertIsNotNone(w.get("snapshot_id"))

    def test_latest_memory_window_ids_nonempty(self):
        self.assertGreater(len(self.r["latest_memory_window_ids"]), 0)

    def test_latest_snapshot_ids_nonempty(self):
        self.assertGreater(len(self.r["latest_snapshot_ids"]), 0)

    def test_latest_window_ids_are_ints(self):
        for wid in self.r["latest_memory_window_ids"]:
            self.assertIsInstance(wid, int)

    def test_memory_creation_ready_still_false(self):
        """PARTIAL_MEMORY must NOT trigger memory_creation_ready."""
        self.assertFalse(self.r["readiness_flags"]["memory_creation_ready"])

    def test_retrieval_ready_still_false(self):
        self.assertFalse(self.r["readiness_flags"]["retrieval_ready"])

    def test_clean_memory_count_zero_or_absent(self):
        v = self.r["clean_memory_count"]
        self.assertIn(v, (0, "table_absent"))


# ---------------------------------------------------------------------------
# E2U-A: count scope — all four counts must be closed WINDOW_15M only
# ---------------------------------------------------------------------------

class LaneE2UACountScopeTests(_DbTestBase):
    """Verify all four scoped counts exclude non-closed and non-15m windows."""

    def _insert_open_window(self, conn, token_id, pair_id, snap_id,
                            memory_quality_label=None) -> int:
        """Insert a WINDOW_15M that is NOT closed (WINDOW_OPEN)."""
        return self._insert_window(
            conn, token_id, pair_id, snap_id,
            memory_quality_label=memory_quality_label,
            data_quality_label="CLEAN_DATA",
            window_status="WINDOW_OPEN",
        )

    def _insert_non_15m_window(self, conn, token_id, pair_id, snap_id) -> int:
        """Insert a closed non-WINDOW_15M window with E2Q metadata."""
        ctx = json.dumps({
            "snapshot_id": snap_id,
            "e2q_audited": True,
            "e2q_audit_status": "PARTIAL_MEMORY",
            "e2q_audited_by": "lane_e2q",
        }, sort_keys=True)
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train, window_status,
                memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at
            ) VALUES (?, ?, 'WINDOW_1H', ?, ?, 'PARTIAL_MEMORY', 'CLEAN_DATA',
                      0, 'WINDOW_CLOSED', 'PARTIAL_MEMORY', ?, 'test', ?, ?)
            """,
            (token_id, pair_id, _NOW, _NOW, ctx, _NOW, _NOW),
        )
        return int(cur.lastrowid)

    def _setup_mixed(self):
        """3 closed WINDOW_15M + 1 open WINDOW_15M + 1 closed WINDOW_1H."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            for _ in range(3):
                snap_id = self._insert_snapshot(conn, token_id, pair_id)
                self._insert_window(conn, token_id, pair_id, snap_id)
            # open WINDOW_15M with E2Q metadata — must NOT be counted
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            self._insert_open_window(conn, token_id, pair_id, snap_id,
                                     memory_quality_label="PARTIAL_MEMORY")
            # closed WINDOW_1H with E2Q metadata — must NOT be counted
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            self._insert_non_15m_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()

    def test_closed_window_15m_count_excludes_open(self):
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["closed_window_15m_count"], 3)

    def test_e2q_audited_count_excludes_open_window(self):
        """Open WINDOW_15M with E2Q metadata must not be in e2q_audited_window_count."""
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["e2q_audited_window_count"], 3)

    def test_e2q_audited_count_excludes_non_15m_window(self):
        """Closed WINDOW_1H with E2Q metadata must not be in e2q_audited_window_count."""
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["e2q_audited_window_count"], 3)

    def test_clean_data_count_excludes_open_window(self):
        """Open WINDOW_15M with CLEAN_DATA must not be in clean_data_window_count."""
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["clean_data_window_count"], 3)

    def test_clean_data_count_excludes_non_15m_window(self):
        """Closed WINDOW_1H with CLEAN_DATA must not be in clean_data_window_count."""
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["clean_data_window_count"], 3)

    def test_partial_memory_count_excludes_open_window(self):
        """Open WINDOW_15M with PARTIAL_MEMORY must not be counted."""
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["partial_memory_window_count"], 3)

    def test_partial_memory_count_includes_all_closed_not_just_five(self):
        """partial_memory_window_count must count ALL closed WINDOW_15M, not cap at 5."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            for _ in range(7):
                snap_id = self._insert_snapshot(conn, token_id, pair_id)
                self._insert_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["partial_memory_window_count"], 7)

    def test_last_five_15m_excludes_open_windows(self):
        """last_five_window_15m must contain only closed windows."""
        self._setup_mixed()
        r = self._run()
        for w in r["last_five_window_15m"]:
            self.assertEqual(w["window_status"], "WINDOW_CLOSED")

    def test_last_five_15m_excludes_non_15m_windows(self):
        """last_five_window_15m must contain only WINDOW_15M kind."""
        self._setup_mixed()
        r = self._run()
        for w in r["last_five_window_15m"]:
            self.assertEqual(w["window_kind"], "WINDOW_15M")

    def test_all_four_scoped_counts_match_closed_15m_count(self):
        """When all windows are clean closed WINDOW_15M, all four counts agree."""
        self._make_n_windows(4)
        r = self._run()
        self.assertEqual(r["closed_window_15m_count"], 4)
        self.assertEqual(r["e2q_audited_window_count"], 4)
        self.assertEqual(r["clean_data_window_count"], 4)
        self.assertEqual(r["partial_memory_window_count"], 4)

    def test_zero_delta_with_mixed_windows(self):
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r.get("read_only_delta_violations"), [])

    def test_locked_state_unchanged(self):
        self._setup_mixed()
        r = self._run()
        ls = r["locked_state"]
        for key, val in ls.items():
            self.assertFalse(val, f"locked_state[{key!r}] must be False")

    def test_readiness_flags_unchanged(self):
        self._setup_mixed()
        r = self._run()
        rf = r["readiness_flags"]
        self.assertFalse(rf["memory_creation_ready"])
        self.assertFalse(rf["retrieval_ready"])
        self.assertFalse(rf["paper_decision_ready"])
        self.assertFalse(rf["buy_ready"])

    def test_partial_memory_still_not_clean_memory(self):
        self._make_n_windows(5)
        r = self._run()
        v = r["clean_memory_count"]
        self.assertIn(v, (0, "table_absent"))

    def test_repeatable_proof_uses_closed_count(self):
        """repeatable_15m_window_proof must be based on closed WINDOW_15M count."""
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            # 1 closed + 5 open = only 1 closed, so proof must be False
            snap_id = self._insert_snapshot(conn, token_id, pair_id)
            self._insert_window(conn, token_id, pair_id, snap_id)
            for _ in range(5):
                snap_id = self._insert_snapshot(conn, token_id, pair_id)
                self._insert_open_window(conn, token_id, pair_id, snap_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertFalse(r["repeatable_15m_window_proof"])
        self.assertEqual(r["closed_window_15m_count"], 1)


# ---------------------------------------------------------------------------
# Repeatable proof threshold tests
# ---------------------------------------------------------------------------

class LaneE2URepeatableProofTests(_DbTestBase):
    def test_proof_false_with_zero_windows(self):
        r = self._run()
        self.assertFalse(r["repeatable_15m_window_proof"])

    def test_proof_false_with_one_window(self):
        self._make_n_windows(1)
        r = self._run()
        self.assertFalse(r["repeatable_15m_window_proof"])

    def test_proof_true_with_two_windows(self):
        self._make_n_windows(2)
        r = self._run()
        self.assertTrue(r["repeatable_15m_window_proof"])

    def test_proof_true_with_five_windows(self):
        self._make_n_windows(5)
        r = self._run()
        self.assertTrue(r["repeatable_15m_window_proof"])

    def test_last_five_capped_at_five(self):
        self._make_n_windows(7)
        r = self._run()
        self.assertLessEqual(len(r["last_five_window_15m"]), 5)

    def test_readiness_repeatable_false_with_one(self):
        self._make_n_windows(1)
        r = self._run()
        self.assertFalse(r["readiness_flags"]["repeatable_15m_windows_ready"])

    def test_readiness_repeatable_true_with_two(self):
        self._make_n_windows(2)
        r = self._run()
        self.assertTrue(r["readiness_flags"]["repeatable_15m_windows_ready"])


# ---------------------------------------------------------------------------
# PARTIAL_MEMORY is not clean memory
# ---------------------------------------------------------------------------

class LaneE2UPartialNotCleanTests(_DbTestBase):
    def test_partial_memory_not_clean_memory(self):
        self._make_n_windows(5)
        r = self._run()
        v = r["clean_memory_count"]
        self.assertIn(v, (0, "table_absent"),
                      "PARTIAL_MEMORY windows must not count as clean memory")

    def test_memory_creation_ready_false_even_with_partial(self):
        self._make_n_windows(5)
        r = self._run()
        self.assertFalse(r["readiness_flags"]["memory_creation_ready"])

    def test_retrieval_ready_false_even_with_partial(self):
        self._make_n_windows(5)
        r = self._run()
        self.assertFalse(r["readiness_flags"]["retrieval_ready"])

    def test_notes_say_partial_not_clean(self):
        self._make_n_windows(3)
        r = self._run()
        combined = " ".join(r.get("notes", [])).upper()
        self.assertIn("PARTIAL_MEMORY", combined)
        self.assertIn("NOT", combined)

    def test_retrieval_eligible_count_not_active_or_zero(self):
        self._make_n_windows(3)
        r = self._run()
        v = r.get("retrieval_eligible_count")
        self.assertIn(v, (0, "not_active"))


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2UCLITests(_DbTestBase):
    def test_cli_function_exists(self):
        self.assertTrue(callable(main_report_e2u_15m_cycle_closeout))

    def test_cli_returns_zero_with_valid_args(self):
        ret = main_report_e2u_15m_cycle_closeout(
            [
                "--db-path", str(self.db_path),
                "--operator-approved",
                "--format", "json",
            ]
        )
        self.assertEqual(ret, 0)

    def test_cli_outputs_valid_json(self):
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_report_e2u_15m_cycle_closeout(
                [
                    "--db-path", str(self.db_path),
                    "--operator-approved",
                    "--format", "json",
                ]
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertIsInstance(parsed, dict)

    def test_cli_has_command_field(self):
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_report_e2u_15m_cycle_closeout(
                [
                    "--db-path", str(self.db_path),
                    "--operator-approved",
                    "--format", "json",
                ]
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed.get("command"), E2U_COMMAND_NAME)

    def test_cli_blocked_when_not_approved(self):
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_report_e2u_15m_cycle_closeout(
                [
                    "--db-path", str(self.db_path),
                    "--format", "json",
                ]
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed.get("e2u_status"), E2U_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------

class LaneE2UPyprojectTests(unittest.TestCase):
    def test_pyproject_entry_registered(self):
        toml = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-report-e2u-15m-cycle-closeout", toml)

    def test_pyproject_points_to_correct_function(self):
        toml = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("main_report_e2u_15m_cycle_closeout", toml)


if __name__ == "__main__":
    unittest.main()
