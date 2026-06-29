"""
Post-Lane 10 Lane E2W -- 5m-to-15m Linkage Verification Report

Tests prove:
- e2w module imports cleanly
- E2W_COMMAND_NAME defined correctly
- E2W_STATUS_READY / E2W_STATUS_BLOCKED defined
- E2W_WINDOW_KIND = 'WINDOW_5M_MICRO_EVENT'
- E2W_PARENT_KIND = 'WINDOW_15M'
- _HARD_LOCKS all True including no_5m_main_outcome, no_clean_memory_from_5m,
  no_scoring_ranking_confidence, no_embeddings_vectors, no_source_governor_bypass,
  no_scheduler_bypass
- _LOCKED_STATE all False
- build_e2w_linkage_report is callable

Blocked gate tests:
- operator_approved=False â†’ E2W_BLOCKED
- db_path=None â†’ E2W_BLOCKED
- db_path missing â†’ E2W_BLOCKED
- blocked result has locked_state all False
- blocked result has hard_locks all True
- blocked result has support_only_confirmed True
- blocked result has main_outcome_blocked True

Happy-path empty DB:
- e2w_status = E2W_REPORT_READY
- operator_approved True in result
- command field matches E2W_COMMAND_NAME
- total_5m_window_count = 0
- valid_linked_5m_count = 0
- dirty_5m_count = 0
- unlinked_5m_count = 0
- invalid_parent_count = 0
- parent_window_15m_count = 0
- repeated_5m_support_proof = False
- multiple_5m_to_one_15m_parent_proof = False
- support_only_confirmed True
- main_outcome_blocked True
- clean_memory_from_5m_blocked True
- retrieval_from_5m_blocked True
- paper_decision_from_5m_blocked True
- buy_from_5m_blocked True
- position_from_5m_blocked True
- locked_state all False
- hard_locks all True
- read_only_delta_violations empty
- next_recommended_lane present

Linkage classification tests:
- valid linked 5m (has parent WINDOW_15M) â†’ valid_linked_5m_count
- unlinked 5m (no parent_window_id in context) â†’ unlinked_5m_count
- 5m with non-15m parent â†’ invalid_parent_count
- dirty 5m (do_not_train=1) â†’ dirty_5m_count
- dirty 5m (DIRTY_DATA quality) â†’ dirty_5m_count
- dirty 5m (DIRTY_MEMORY quality label) â†’ dirty_5m_count
- dirty is reported even if parent present

Proof flag tests:
- repeated_5m_support_proof True when same token/pair has â‰¥2 5m windows
- repeated_5m_support_proof False with only one 5m window
- multiple_5m_to_one_15m_parent_proof True when â‰¥2 valid 5m windows share parent
- multiple_5m_to_one_15m_parent_proof False with distinct parents
- parent_window_15m_count counts distinct referenced 15m ids

Read-only contract:
- zero delta on printer_memory_windows after report
- zero delta on printer_memories after report
- zero delta on printer_paper_decisions after report
- zero delta on printer_paper_positions after report
- zero delta on printer_paper_trade_events after report
- zero delta on printer_paper_trade_audits after report
- no memories created
- no paper decisions created
- no paper positions created

last_n_5m_windows content:
- entries have classification field
- entries have parent_window_id field
- entries have do_not_train field
- entries have memory_quality_label field
- valid linked entries have parent_window_id not None
- unlinked entries have parent_window_id None

Safety flag tests (all True by definition):
- 5m cannot become main outcome memory
- 5m cannot produce CLEAN_MEMORY
- 5m cannot activate retrieval
- 5m cannot create paper decisions
- 5m cannot unlock BUY/SELL/HOLD
- 5m cannot create positions
- no scoring/ranking/confidence lock
- no embeddings/vectors lock

CLI tests:
- main_report_e2w_5m_linkage is callable
- CLI returns 0 with valid args
- CLI outputs valid JSON
- CLI blocked when --operator-approved not set
- pyproject entry registered

E2V tests still import cleanly (cross-check):
- validate_5m_micro_event_evidence still callable
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
from printer_v1.operator_cli.e2w_5m_linkage_report import (
    E2W_COMMAND_NAME,
    E2W_PARENT_KIND,
    E2W_STATUS_BLOCKED,
    E2W_STATUS_READY,
    E2W_WINDOW_KIND,
    _HARD_LOCKS,
    _LOCKED_STATE,
    build_e2w_linkage_report,
)
from printer_v1.operator_cli.commands import main_report_e2w_5m_linkage
from printer_v1.operator_cli.e2v_5m_micro_event_evidence import (
    insert_5m_evidence_window,
    validate_5m_micro_event_evidence,
)


_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR = "E2WTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_NOW = "2026-06-28T10:00:00+00:00"


class _DbBase(unittest.TestCase):
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

    def _count(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            r = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return r[0] if r else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _run(self, **kw) -> dict:
        kw.setdefault("db_path", self.db_path)
        kw.setdefault("operator_approved", True)
        return build_e2w_linkage_report(**kw)

    # ---- fixture helpers ----

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

    def _insert_15m_window(self, conn, token_id: int, pair_id: int) -> int:
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                created_by_phase, created_at, updated_at
            ) VALUES (?, ?, 'WINDOW_15M', ?, ?, 'PARTIAL_MEMORY', 'CLEAN_DATA',
                      0, 'WINDOW_CLOSED', 'PARTIAL_MEMORY', 'lane_e2o', ?, ?)
            """,
            (token_id, pair_id, _NOW, _NOW, _NOW, _NOW),
        )
        return int(cur.lastrowid)

    def _insert_5m(self, conn, token_id: int, pair_id: int,
                   parent_window_id: int | None = None, **kw) -> int:
        return insert_5m_evidence_window(
            conn,
            token_id=token_id,
            pair_id=pair_id,
            parent_window_id=parent_window_id,
            **kw,
        )

    def _base(self):
        """Return (token_id, pair_id, window_15m_id) committed to DB."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid = self._insert_15m_window(conn, tid, pid)
            conn.commit()
        finally:
            conn.close()
        return tid, pid, wid


# ---------------------------------------------------------------------------
# Import and constant tests
# ---------------------------------------------------------------------------

class LaneE2WImportTests(unittest.TestCase):
    def test_module_imports(self):
        from printer_v1.operator_cli import e2w_5m_linkage_report
        self.assertIsNotNone(e2w_5m_linkage_report)

    def test_command_name(self):
        self.assertEqual(E2W_COMMAND_NAME, "printer-report-e2w-5m-linkage")

    def test_status_ready(self):
        self.assertEqual(E2W_STATUS_READY, "E2W_REPORT_READY")

    def test_status_blocked(self):
        self.assertEqual(E2W_STATUS_BLOCKED, "E2W_BLOCKED")

    def test_window_kind(self):
        self.assertEqual(E2W_WINDOW_KIND, "WINDOW_5M_MICRO_EVENT")

    def test_parent_kind(self):
        self.assertEqual(E2W_PARENT_KIND, "WINDOW_15M")

    def test_hard_locks_all_true(self):
        for k, v in _HARD_LOCKS.items():
            self.assertTrue(v, f"_HARD_LOCKS[{k!r}] must be True")

    def test_hard_lock_no_5m_main_outcome(self):
        self.assertTrue(_HARD_LOCKS["no_5m_main_outcome"])

    def test_hard_lock_no_clean_memory_from_5m(self):
        self.assertTrue(_HARD_LOCKS["no_clean_memory_from_5m"])

    def test_hard_lock_no_scoring_ranking_confidence(self):
        self.assertTrue(_HARD_LOCKS["no_scoring_ranking_confidence"])

    def test_hard_lock_no_embeddings_vectors(self):
        self.assertTrue(_HARD_LOCKS["no_embeddings_vectors"])

    def test_hard_lock_no_source_governor_bypass(self):
        self.assertTrue(_HARD_LOCKS["no_source_governor_bypass"])

    def test_hard_lock_no_scheduler_bypass(self):
        self.assertTrue(_HARD_LOCKS["no_scheduler_bypass"])

    def test_hard_lock_no_retrieval_activation(self):
        self.assertTrue(_HARD_LOCKS["no_retrieval_activation"])

    def test_hard_lock_no_paper_decisions(self):
        self.assertTrue(_HARD_LOCKS["no_paper_decisions"])

    def test_hard_lock_no_buy_sell_hold(self):
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_locked_state_all_false(self):
        for k, v in _LOCKED_STATE.items():
            self.assertFalse(v, f"_LOCKED_STATE[{k!r}] must be False")

    def test_function_callable(self):
        self.assertTrue(callable(build_e2w_linkage_report))


# ---------------------------------------------------------------------------
# Blocked gate tests
# ---------------------------------------------------------------------------

class LaneE2WBlockedTests(_DbBase):
    def test_blocked_not_approved(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["e2w_status"], E2W_STATUS_BLOCKED)

    def test_blocked_has_reasons_not_approved(self):
        r = self._run(operator_approved=False)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_blocked_db_path_none(self):
        r = build_e2w_linkage_report(None, operator_approved=True)
        self.assertEqual(r["e2w_status"], E2W_STATUS_BLOCKED)

    def test_blocked_db_path_missing(self):
        r = build_e2w_linkage_report(
            pathlib.Path(self._tmp.name) / "no.sqlite3",
            operator_approved=True,
        )
        self.assertEqual(r["e2w_status"], E2W_STATUS_BLOCKED)

    def test_blocked_locked_state_all_false(self):
        r = self._run(operator_approved=False)
        for k, v in r["locked_state"].items():
            self.assertFalse(v, f"locked_state[{k!r}] must be False")

    def test_blocked_hard_locks_all_true(self):
        r = self._run(operator_approved=False)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True")

    def test_blocked_support_only_confirmed(self):
        r = self._run(operator_approved=False)
        self.assertTrue(r["support_only_confirmed"])

    def test_blocked_main_outcome_blocked(self):
        r = self._run(operator_approved=False)
        self.assertTrue(r["main_outcome_blocked"])


# ---------------------------------------------------------------------------
# Happy path: empty DB
# ---------------------------------------------------------------------------

class LaneE2WEmptyDbTests(_DbBase):
    def setUp(self):
        super().setUp()
        self.r = self._run()

    def test_status_ready(self):
        self.assertEqual(self.r["e2w_status"], E2W_STATUS_READY)

    def test_operator_approved_true(self):
        self.assertTrue(self.r["operator_approved"])

    def test_command_field(self):
        self.assertEqual(self.r["command"], E2W_COMMAND_NAME)

    def test_total_5m_count_zero(self):
        self.assertEqual(self.r["total_5m_window_count"], 0)

    def test_valid_linked_count_zero(self):
        self.assertEqual(self.r["valid_linked_5m_count"], 0)

    def test_dirty_count_zero(self):
        self.assertEqual(self.r["dirty_5m_count"], 0)

    def test_unlinked_count_zero(self):
        self.assertEqual(self.r["unlinked_5m_count"], 0)

    def test_invalid_parent_count_zero(self):
        self.assertEqual(self.r["invalid_parent_count"], 0)

    def test_parent_15m_count_zero(self):
        self.assertEqual(self.r["parent_window_15m_count"], 0)

    def test_repeated_proof_false(self):
        self.assertFalse(self.r["repeated_5m_support_proof"])

    def test_multiple_parent_proof_false(self):
        self.assertFalse(self.r["multiple_5m_to_one_15m_parent_proof"])

    def test_support_only_confirmed(self):
        self.assertTrue(self.r["support_only_confirmed"])

    def test_main_outcome_blocked(self):
        self.assertTrue(self.r["main_outcome_blocked"])

    def test_clean_memory_from_5m_blocked(self):
        self.assertTrue(self.r["clean_memory_from_5m_blocked"])

    def test_retrieval_from_5m_blocked(self):
        self.assertTrue(self.r["retrieval_from_5m_blocked"])

    def test_paper_decision_from_5m_blocked(self):
        self.assertTrue(self.r["paper_decision_from_5m_blocked"])

    def test_buy_from_5m_blocked(self):
        self.assertTrue(self.r["buy_from_5m_blocked"])

    def test_position_from_5m_blocked(self):
        self.assertTrue(self.r["position_from_5m_blocked"])

    def test_locked_state_all_false(self):
        for k, v in self.r["locked_state"].items():
            self.assertFalse(v)

    def test_hard_locks_all_true(self):
        for k, v in self.r["hard_locks"].items():
            self.assertTrue(v)

    def test_read_only_delta_violations_empty(self):
        self.assertEqual(self.r["read_only_delta_violations"], [])

    def test_next_recommended_lane_present(self):
        self.assertIsInstance(self.r["next_recommended_lane"], str)
        self.assertGreater(len(self.r["next_recommended_lane"]), 5)

    def test_result_json_serializable(self):
        json.dumps(self.r)

    def test_last_n_5m_windows_empty(self):
        self.assertEqual(self.r["last_n_5m_windows"], [])


# ---------------------------------------------------------------------------
# Linkage classification: valid linked
# ---------------------------------------------------------------------------

class LaneE2WValidLinkedTests(_DbBase):
    def test_valid_linked_counted(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["valid_linked_5m_count"], 1)
        self.assertEqual(r["total_5m_window_count"], 1)
        self.assertEqual(r["unlinked_5m_count"], 0)
        self.assertEqual(r["invalid_parent_count"], 0)
        self.assertEqual(r["dirty_5m_count"], 0)

    def test_valid_linked_parent_15m_count(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["parent_window_15m_count"], 1)

    def test_valid_linked_entry_has_parent_id(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        entry = r["last_n_5m_windows"][0]
        self.assertEqual(entry["parent_window_id"], wid)

    def test_valid_linked_entry_classification(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        entry = r["last_n_5m_windows"][0]
        self.assertEqual(entry["classification"], "valid_linked")

    def test_valid_linked_5m_cannot_replace_15m(self):
        """15m window count stays at 1 even with linked 5m."""
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        # Only one WINDOW_15M row exists
        conn2 = self._connect()
        try:
            count_15m = conn2.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
                " WHERE window_kind = 'WINDOW_15M'"
            ).fetchone()[0]
        finally:
            conn2.close()
        self.assertEqual(count_15m, 1)


# ---------------------------------------------------------------------------
# Linkage classification: unlinked
# ---------------------------------------------------------------------------

class LaneE2WUnlinkedTests(_DbBase):
    def _insert_unlinked_5m(self, token_id, pair_id) -> int:
        """Insert 5m window with no parent_window_id in context."""
        conn = self._connect()
        try:
            # Override supporting_context_json to omit parent_window_id
            ctx = json.dumps({"created_by": "lane_e2v"})
            now = _NOW
            cur = conn.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, closed_at,
                    memory_status, data_quality_label, do_not_train,
                    window_status, memory_quality_label,
                    supporting_context_json, created_by_phase, created_at, updated_at
                ) VALUES (?, ?, 'WINDOW_5M_MICRO_EVENT', ?, ?, 'PARTIAL_MEMORY',
                          'CLEAN_DATA', 0, 'WINDOW_CLOSED', 'SUPPORT_EVIDENCE',
                          ?, 'lane_e2v', ?, ?)
                """,
                (token_id, pair_id, now, now, ctx, now, now),
            )
            wid = int(cur.lastrowid)
            conn.commit()
        finally:
            conn.close()
        return wid

    def test_unlinked_counted(self):
        tid, pid, _ = self._base()
        self._insert_unlinked_5m(tid, pid)
        r = self._run()
        self.assertEqual(r["unlinked_5m_count"], 1)
        self.assertEqual(r["valid_linked_5m_count"], 0)

    def test_unlinked_entry_parent_id_none(self):
        tid, pid, _ = self._base()
        self._insert_unlinked_5m(tid, pid)
        r = self._run()
        entry = r["last_n_5m_windows"][0]
        self.assertIsNone(entry["parent_window_id"])

    def test_unlinked_entry_classification(self):
        tid, pid, _ = self._base()
        self._insert_unlinked_5m(tid, pid)
        r = self._run()
        entry = r["last_n_5m_windows"][0]
        self.assertEqual(entry["classification"], "unlinked")

    def test_unlinked_parent_15m_count_zero(self):
        tid, pid, _ = self._base()
        self._insert_unlinked_5m(tid, pid)
        r = self._run()
        self.assertEqual(r["parent_window_15m_count"], 0)


# ---------------------------------------------------------------------------
# Linkage classification: invalid parent (non-15m parent)
# ---------------------------------------------------------------------------

class LaneE2WInvalidParentTests(_DbBase):
    def _insert_non_15m_parent(self, conn, token_id, pair_id) -> int:
        """Insert a closed WINDOW_1H to use as a bogus parent."""
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                created_by_phase, created_at, updated_at
            ) VALUES (?, ?, 'WINDOW_1H', ?, ?, 'PARTIAL_MEMORY', 'CLEAN_DATA',
                      0, 'WINDOW_CLOSED', 'PARTIAL_MEMORY', 'test', ?, ?)
            """,
            (token_id, pair_id, _NOW, _NOW, _NOW, _NOW),
        )
        return int(cur.lastrowid)

    def test_non_15m_parent_counted_invalid(self):
        tid, pid, _ = self._base()
        conn = self._connect()
        try:
            bogus_id = self._insert_non_15m_parent(conn, tid, pid)
            self._insert_5m(conn, tid, pid, parent_window_id=bogus_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["invalid_parent_count"], 1)
        self.assertEqual(r["valid_linked_5m_count"], 0)

    def test_non_15m_parent_entry_classification(self):
        tid, pid, _ = self._base()
        conn = self._connect()
        try:
            bogus_id = self._insert_non_15m_parent(conn, tid, pid)
            self._insert_5m(conn, tid, pid, parent_window_id=bogus_id)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        entry = r["last_n_5m_windows"][0]
        self.assertEqual(entry["classification"], "invalid_parent")

    def test_nonexistent_parent_id_counted_invalid(self):
        tid, pid, _ = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=99999)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["invalid_parent_count"], 1)


# ---------------------------------------------------------------------------
# Linkage classification: dirty
# ---------------------------------------------------------------------------

class LaneE2WDirtyTests(_DbBase):
    def test_dirty_do_not_train_flag(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(
                conn, tid, pid, parent_window_id=wid,
                do_not_train=1,
                memory_quality_label="DIRTY_MEMORY",
                memory_status="DIRTY_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["dirty_5m_count"], 1)
        self.assertEqual(r["valid_linked_5m_count"], 0)

    def test_dirty_data_quality_label(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(
                conn, tid, pid, parent_window_id=wid,
                data_quality_label="DIRTY_DATA",
                memory_status="DIRTY_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["dirty_5m_count"], 1)

    def test_dirty_memory_quality_label(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(
                conn, tid, pid, parent_window_id=wid,
                memory_quality_label="DIRTY_MEMORY",
                memory_status="DIRTY_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["dirty_5m_count"], 1)

    def test_dirty_classified_even_with_parent(self):
        """Dirty classification takes precedence over valid parent."""
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(
                conn, tid, pid, parent_window_id=wid,
                do_not_train=1,
                memory_quality_label="DIRTY_MEMORY",
                memory_status="DIRTY_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["dirty_5m_count"], 1)
        self.assertEqual(r["valid_linked_5m_count"], 0)

    def test_dirty_entry_classification(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(
                conn, tid, pid, parent_window_id=wid,
                do_not_train=1,
                memory_quality_label="DIRTY_MEMORY",
                memory_status="DIRTY_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        entry = r["last_n_5m_windows"][0]
        self.assertEqual(entry["classification"], "dirty")

    def test_dirty_entry_has_do_not_train_true(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(
                conn, tid, pid, parent_window_id=wid,
                do_not_train=1,
                memory_quality_label="DIRTY_MEMORY",
                memory_status="DIRTY_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        entry = r["last_n_5m_windows"][0]
        self.assertTrue(entry["do_not_train"])


# ---------------------------------------------------------------------------
# Mixed classification: multiple 5m windows
# ---------------------------------------------------------------------------

class LaneE2WMixedTests(_DbBase):
    def _setup_mixed(self):
        """1 valid_linked + 1 unlinked + 1 dirty."""
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            # valid linked
            self._insert_5m(conn, tid, pid, parent_window_id=wid,
                            opened_at="2026-06-28T10:00:00+00:00",
                            closed_at="2026-06-28T10:05:00+00:00")
            # dirty
            self._insert_5m(conn, tid, pid, parent_window_id=wid,
                            do_not_train=1,
                            memory_quality_label="DIRTY_MEMORY",
                            memory_status="DIRTY_MEMORY",
                            opened_at="2026-06-28T10:05:00+00:00",
                            closed_at="2026-06-28T10:10:00+00:00")
            # unlinked (no ctx parent_window_id) â€” use raw INSERT
            ctx = json.dumps({"created_by": "lane_e2v"})
            conn.execute(
                """
                INSERT INTO printer_memory_windows (
                    token_id, pair_id, window_kind, opened_at, closed_at,
                    memory_status, data_quality_label, do_not_train,
                    window_status, memory_quality_label,
                    supporting_context_json, created_by_phase, created_at, updated_at
                ) VALUES (?, ?, 'WINDOW_5M_MICRO_EVENT', ?, ?, 'PARTIAL_MEMORY',
                          'CLEAN_DATA', 0, 'WINDOW_CLOSED', 'SUPPORT_EVIDENCE',
                          ?, 'lane_e2v', ?, ?)
                """,
                (tid, pid, "2026-06-28T10:10:00+00:00",
                 "2026-06-28T10:15:00+00:00", ctx, _NOW, _NOW),
            )
            conn.commit()
        finally:
            conn.close()
        return tid, pid, wid

    def test_mixed_total_count(self):
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["total_5m_window_count"], 3)

    def test_mixed_valid_linked_count(self):
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["valid_linked_5m_count"], 1)

    def test_mixed_dirty_count(self):
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["dirty_5m_count"], 1)

    def test_mixed_unlinked_count(self):
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["unlinked_5m_count"], 1)

    def test_mixed_zero_delta(self):
        self._setup_mixed()
        r = self._run()
        self.assertEqual(r["read_only_delta_violations"], [])


# ---------------------------------------------------------------------------
# Proof flag tests
# ---------------------------------------------------------------------------

class LaneE2WProofFlagTests(_DbBase):
    def test_repeated_proof_false_one_window(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertFalse(r["repeated_5m_support_proof"])

    def test_repeated_proof_true_two_windows_same_pair(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid,
                            opened_at="2026-06-28T10:00:00+00:00",
                            closed_at="2026-06-28T10:05:00+00:00")
            self._insert_5m(conn, tid, pid, parent_window_id=wid,
                            opened_at="2026-06-28T10:05:00+00:00",
                            closed_at="2026-06-28T10:10:00+00:00")
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertTrue(r["repeated_5m_support_proof"])

    def test_multiple_5m_to_one_15m_parent_proof_false(self):
        """Two 5m windows linked to different 15m parents."""
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid1 = self._insert_15m_window(conn, tid, pid)
            wid2 = self._insert_15m_window(conn, tid, pid)
            self._insert_5m(conn, tid, pid, parent_window_id=wid1,
                            opened_at="2026-06-28T10:00:00+00:00",
                            closed_at="2026-06-28T10:05:00+00:00")
            self._insert_5m(conn, tid, pid, parent_window_id=wid2,
                            opened_at="2026-06-28T10:05:00+00:00",
                            closed_at="2026-06-28T10:10:00+00:00")
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertFalse(r["multiple_5m_to_one_15m_parent_proof"])

    def test_multiple_5m_to_one_15m_parent_proof_true(self):
        """Two valid 5m windows sharing the same parent."""
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid,
                            opened_at="2026-06-28T10:00:00+00:00",
                            closed_at="2026-06-28T10:05:00+00:00")
            self._insert_5m(conn, tid, pid, parent_window_id=wid,
                            opened_at="2026-06-28T10:05:00+00:00",
                            closed_at="2026-06-28T10:10:00+00:00")
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertTrue(r["multiple_5m_to_one_15m_parent_proof"])

    def test_parent_window_15m_count_two_distinct_parents(self):
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid1 = self._insert_15m_window(conn, tid, pid)
            wid2 = self._insert_15m_window(conn, tid, pid)
            self._insert_5m(conn, tid, pid, parent_window_id=wid1,
                            opened_at="2026-06-28T10:00:00+00:00",
                            closed_at="2026-06-28T10:05:00+00:00")
            self._insert_5m(conn, tid, pid, parent_window_id=wid2,
                            opened_at="2026-06-28T10:05:00+00:00",
                            closed_at="2026-06-28T10:10:00+00:00")
            conn.commit()
        finally:
            conn.close()
        r = self._run()
        self.assertEqual(r["parent_window_15m_count"], 2)


# ---------------------------------------------------------------------------
# Read-only contract
# ---------------------------------------------------------------------------

class LaneE2WReadOnlyTests(_DbBase):
    def test_zero_delta_empty_db(self):
        r = self._run()
        self.assertEqual(r["read_only_delta_violations"], [])

    def test_zero_delta_with_5m_rows(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        before = self._count("printer_memory_windows")
        r = self._run()
        after = self._count("printer_memory_windows")
        self.assertEqual(before, after)
        self.assertEqual(r["read_only_delta_violations"], [])

    def test_no_memories_created(self):
        before = self._count("printer_memories")
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        self._run()
        self.assertEqual(self._count("printer_memories"), before)

    def test_no_paper_decisions_created(self):
        before = self._count("printer_paper_decisions")
        self._run()
        self.assertEqual(self._count("printer_paper_decisions"), before)

    def test_no_paper_positions_created(self):
        before = self._count("printer_paper_positions")
        self._run()
        self.assertEqual(self._count("printer_paper_positions"), before)

    def test_no_paper_trade_events_created(self):
        before = self._count("printer_paper_trade_events")
        self._run()
        self.assertEqual(self._count("printer_paper_trade_events"), before)

    def test_no_paper_trade_audits_created(self):
        before = self._count("printer_paper_trade_audits")
        self._run()
        self.assertEqual(self._count("printer_paper_trade_audits"), before)


# ---------------------------------------------------------------------------
# Safety flag tests
# ---------------------------------------------------------------------------

class LaneE2WSafetyFlagTests(_DbBase):
    def test_5m_cannot_be_main_outcome(self):
        r = self._run()
        self.assertTrue(r["main_outcome_blocked"])

    def test_5m_cannot_produce_clean_memory(self):
        r = self._run()
        self.assertTrue(r["clean_memory_from_5m_blocked"])

    def test_5m_cannot_activate_retrieval(self):
        r = self._run()
        self.assertTrue(r["retrieval_from_5m_blocked"])

    def test_5m_cannot_create_paper_decisions(self):
        r = self._run()
        self.assertTrue(r["paper_decision_from_5m_blocked"])

    def test_5m_cannot_unlock_buy(self):
        r = self._run()
        self.assertTrue(r["buy_from_5m_blocked"])

    def test_5m_cannot_create_positions(self):
        r = self._run()
        self.assertTrue(r["position_from_5m_blocked"])

    def test_no_scoring_ranking_lock(self):
        r = self._run()
        self.assertTrue(r["hard_locks"]["no_scoring_ranking_confidence"])

    def test_no_embeddings_vectors_lock(self):
        r = self._run()
        self.assertTrue(r["hard_locks"]["no_embeddings_vectors"])

    def test_locked_state_buy_false(self):
        r = self._run()
        self.assertFalse(r["locked_state"]["buy_unlock"])

    def test_locked_state_sell_false(self):
        r = self._run()
        self.assertFalse(r["locked_state"]["sell_unlock"])

    def test_locked_state_hold_false(self):
        r = self._run()
        self.assertFalse(r["locked_state"]["hold_unlock"])

    def test_locked_state_pnl_false(self):
        r = self._run()
        self.assertFalse(r["locked_state"]["pnl_unlock"])

    def test_locked_state_live_execution_false(self):
        r = self._run()
        self.assertFalse(r["locked_state"]["live_execution"])

    def test_locked_state_wallet_false(self):
        r = self._run()
        self.assertFalse(r["locked_state"]["wallet_private_key"])


# ---------------------------------------------------------------------------
# last_n_5m_windows entry structure
# ---------------------------------------------------------------------------

class LaneE2WEntryStructureTests(_DbBase):
    def _make_one(self):
        tid, pid, wid = self._base()
        conn = self._connect()
        try:
            self._insert_5m(conn, tid, pid, parent_window_id=wid)
            conn.commit()
        finally:
            conn.close()
        return self._run()

    def test_entry_has_classification(self):
        r = self._make_one()
        self.assertIn("classification", r["last_n_5m_windows"][0])

    def test_entry_has_parent_window_id(self):
        r = self._make_one()
        self.assertIn("parent_window_id", r["last_n_5m_windows"][0])

    def test_entry_has_do_not_train(self):
        r = self._make_one()
        self.assertIn("do_not_train", r["last_n_5m_windows"][0])

    def test_entry_has_memory_quality_label(self):
        r = self._make_one()
        self.assertIn("memory_quality_label", r["last_n_5m_windows"][0])

    def test_entry_has_data_quality_label(self):
        r = self._make_one()
        self.assertIn("data_quality_label", r["last_n_5m_windows"][0])

    def test_entry_has_token_id(self):
        r = self._make_one()
        self.assertIn("token_id", r["last_n_5m_windows"][0])

    def test_valid_entry_parent_id_not_none(self):
        r = self._make_one()
        entry = r["last_n_5m_windows"][0]
        self.assertEqual(entry["classification"], "valid_linked")
        self.assertIsNotNone(entry["parent_window_id"])


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2WCLITests(_DbBase):
    def test_cli_function_callable(self):
        self.assertTrue(callable(main_report_e2w_5m_linkage))

    def test_cli_returns_zero_valid_args(self):
        ret = main_report_e2w_5m_linkage([
            "--db-path", str(self.db_path),
            "--operator-approved",
            "--format", "json",
        ])
        self.assertEqual(ret, 0)

    def test_cli_outputs_valid_json(self):
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            main_report_e2w_5m_linkage([
                "--db-path", str(self.db_path),
                "--operator-approved",
                "--format", "json",
            ])
        finally:
            sys.stdout = old
        parsed = json.loads(captured.getvalue())
        self.assertIsInstance(parsed, dict)

    def test_cli_command_field(self):
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            main_report_e2w_5m_linkage([
                "--db-path", str(self.db_path),
                "--operator-approved",
                "--format", "json",
            ])
        finally:
            sys.stdout = old
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed["command"], E2W_COMMAND_NAME)

    def test_cli_blocked_without_flag(self):
        captured = io.StringIO()
        old = sys.stdout
        sys.stdout = captured
        try:
            main_report_e2w_5m_linkage([
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        finally:
            sys.stdout = old
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed["e2w_status"], E2W_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# pyproject.toml
# ---------------------------------------------------------------------------

class LaneE2WPyprojectTests(unittest.TestCase):
    def test_pyproject_entry_registered(self):
        toml = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-report-e2w-5m-linkage", toml)

    def test_pyproject_points_to_correct_function(self):
        toml = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("main_report_e2w_5m_linkage", toml)


# ---------------------------------------------------------------------------
# Cross-check: E2V still works
# ---------------------------------------------------------------------------

class LaneE2WE2VCrossCheckTests(unittest.TestCase):
    def test_e2v_validate_still_callable(self):
        self.assertTrue(callable(validate_5m_micro_event_evidence))

    def test_e2v_valid_fixture_still_valid(self):
        from printer_v1.operator_cli.e2v_5m_micro_event_evidence import (
            E2V_STATUS_VALID,
            build_5m_evidence_fixture,
        )
        r = validate_5m_micro_event_evidence(build_5m_evidence_fixture())
        self.assertEqual(r["e2v_status"], E2V_STATUS_VALID)

    def test_e2v_blocked_no_parent_still_blocked(self):
        from printer_v1.operator_cli.e2v_5m_micro_event_evidence import (
            E2V_STATUS_BLOCKED,
            build_5m_evidence_fixture,
        )
        r = validate_5m_micro_event_evidence(
            build_5m_evidence_fixture(parent_window_id=None)
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)


if __name__ == "__main__":
    unittest.main()
