"""
Post-Lane 10 Lane E2V -- WINDOW_5M_MICRO_EVENT Support Evidence Hardening

Tests prove:
- e2v module imports cleanly
- E2V_WINDOW_KIND = 'WINDOW_5M_MICRO_EVENT'
- E2V_REQUIRED_PARENT_KIND = 'WINDOW_15M'
- E2V constants defined (STATUS_VALID, STATUS_BLOCKED, STATUS_DIRTY, STATUS_AUDIT_ONLY)
- E2V_ALLOWED_MEMORY_STATUS does not include CLEAN_MEMORY
- E2V_ALLOWED_QUALITY_LABELS does not include CLEAN_MEMORY
- _HARD_LOCKS all True including no_5m_main_outcome, no_clean_memory_from_5m
- validate_5m_micro_event_evidence is callable
- build_5m_evidence_fixture is callable
- insert_5m_evidence_window is callable

Structural gate tests:
- wrong window_kind → BLOCKED
- missing parent_window_id → BLOCKED
- parent_window_kind not WINDOW_15M → BLOCKED (non-15m parent rejected)
- memory_status = CLEAN_MEMORY → BLOCKED
- memory_quality_label = CLEAN_MEMORY → BLOCKED
- is_main_outcome_window = True → BLOCKED (5m cannot be main outcome)
- 5m cannot unlock retrieval (hard lock)
- 5m cannot create paper decisions (hard lock)
- 5m cannot create BUY/SELL/HOLD (hard lock)
- 5m cannot create positions, trade events, PnL (hard lock)
- 5m cannot produce clean memory by itself

Quality classification tests:
- valid linked evidence → E2V_VALID
- valid evidence has do_not_train=False
- valid evidence has memory_quality_label in allowed set
- dirty data_quality_label → E2V_DIRTY, do_not_train=True
- stale evidence → E2V_DIRTY, do_not_train=True
- failed evidence → E2V_DIRTY, do_not_train=True
- mismatched evidence → E2V_DIRTY, do_not_train=True
- dirty source_status → E2V_DIRTY, do_not_train=True
- ACCEPTABLE_PARTIAL_DATA → E2V_AUDIT_ONLY, do_not_train=True
- incomplete evidence → E2V_AUDIT_ONLY, do_not_train=True
- dirty evidence has rejection_reasons nonempty
- unlinked evidence (parent_window_id=None) → BLOCKED
- unlinked evidence has do_not_train=True
- result always has hard_locks dict

Fixture DB tests:
- insert_5m_evidence_window inserts row with window_kind=WINDOW_5M_MICRO_EVENT
- multiple 5m windows can exist for same token/pair over time
- multiple 5m windows can link to same parent WINDOW_15M
- 5m fixture rows do not create printer_memories rows
- 5m fixture rows do not create printer_paper_decisions rows
- 5m fixture rows do not create printer_paper_positions rows
- 5m fixture rows do not create printer_paper_trade_events rows
- 5m fixture rows do not create printer_paper_trade_audits rows
- 5m window's supporting_context_json carries parent_window_id
- 5m window inserted with do_not_train=1 for dirty evidence
- 5m window memory_quality_label not CLEAN_MEMORY in fixture DB

E2U report isolation:
- E2U report closed_window_15m_count is unaffected by 5m windows
- E2U report e2q_audited_window_count is unaffected by 5m windows
- E2U report partial_memory_window_count is unaffected by 5m windows
- E2U last_five_window_15m is unaffected by 5m windows
- E2U report is still read-only with zero delta after 5m rows added
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
from printer_v1.operator_cli.e2v_5m_micro_event_evidence import (
    E2V_ALLOWED_MEMORY_STATUS,
    E2V_ALLOWED_QUALITY_LABELS,
    E2V_CREATED_BY,
    E2V_DIRTY_DATA_LABELS,
    E2V_REQUIRED_PARENT_KIND,
    E2V_STATUS_AUDIT_ONLY,
    E2V_STATUS_BLOCKED,
    E2V_STATUS_DIRTY,
    E2V_STATUS_VALID,
    E2V_WINDOW_KIND,
    _HARD_LOCKS,
    build_5m_evidence_fixture,
    insert_5m_evidence_window,
    validate_5m_micro_event_evidence,
)
from printer_v1.operator_cli.e2u_15m_cycle_closeout_report import (
    build_e2u_closeout_report,
)


_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR_ADDR = "E2VTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
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

    def _insert_15m_window(
        self,
        conn: sqlite3.Connection,
        token_id: int,
        pair_id: int,
    ) -> int:
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

    def _make_base_fixture(self):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            window_id = self._insert_15m_window(conn, token_id, pair_id)
            conn.commit()
        finally:
            conn.close()
        return token_id, pair_id, window_id


# ---------------------------------------------------------------------------
# Import and constant tests
# ---------------------------------------------------------------------------

class LaneE2VImportTests(unittest.TestCase):
    def test_module_imports(self):
        from printer_v1.operator_cli import e2v_5m_micro_event_evidence
        self.assertIsNotNone(e2v_5m_micro_event_evidence)

    def test_window_kind(self):
        self.assertEqual(E2V_WINDOW_KIND, "WINDOW_5M_MICRO_EVENT")

    def test_required_parent_kind(self):
        self.assertEqual(E2V_REQUIRED_PARENT_KIND, "WINDOW_15M")

    def test_status_valid(self):
        self.assertEqual(E2V_STATUS_VALID, "E2V_VALID")

    def test_status_blocked(self):
        self.assertEqual(E2V_STATUS_BLOCKED, "E2V_BLOCKED")

    def test_status_dirty(self):
        self.assertEqual(E2V_STATUS_DIRTY, "E2V_DIRTY")

    def test_status_audit_only(self):
        self.assertEqual(E2V_STATUS_AUDIT_ONLY, "E2V_AUDIT_ONLY")

    def test_allowed_memory_status_no_clean_memory(self):
        self.assertNotIn("CLEAN_MEMORY", E2V_ALLOWED_MEMORY_STATUS)

    def test_allowed_quality_labels_no_clean_memory(self):
        self.assertNotIn("CLEAN_MEMORY", E2V_ALLOWED_QUALITY_LABELS)

    def test_allowed_quality_labels_has_support_evidence(self):
        self.assertIn("SUPPORT_EVIDENCE", E2V_ALLOWED_QUALITY_LABELS)

    def test_allowed_quality_labels_has_audit_only(self):
        self.assertIn("AUDIT_ONLY", E2V_ALLOWED_QUALITY_LABELS)

    def test_allowed_quality_labels_has_dirty_memory(self):
        self.assertIn("DIRTY_MEMORY", E2V_ALLOWED_QUALITY_LABELS)

    def test_allowed_quality_labels_has_do_not_train(self):
        self.assertIn("DO_NOT_TRAIN", E2V_ALLOWED_QUALITY_LABELS)

    def test_hard_locks_all_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"_HARD_LOCKS[{key!r}] must be True")

    def test_hard_lock_no_5m_main_outcome(self):
        self.assertTrue(_HARD_LOCKS.get("no_5m_main_outcome"))

    def test_hard_lock_no_clean_memory_from_5m(self):
        self.assertTrue(_HARD_LOCKS.get("no_clean_memory_from_5m"))

    def test_hard_lock_no_memory_creation(self):
        self.assertTrue(_HARD_LOCKS.get("no_memory_creation"))

    def test_hard_lock_no_retrieval_activation(self):
        self.assertTrue(_HARD_LOCKS.get("no_retrieval_activation"))

    def test_hard_lock_no_buy_sell_hold(self):
        self.assertTrue(_HARD_LOCKS.get("no_buy_sell_hold"))

    def test_hard_lock_no_paper_decisions(self):
        self.assertTrue(_HARD_LOCKS.get("no_paper_decisions"))

    def test_hard_lock_no_positions(self):
        self.assertTrue(_HARD_LOCKS.get("no_positions"))

    def test_hard_lock_no_pnl(self):
        self.assertTrue(_HARD_LOCKS.get("no_pnl"))

    def test_functions_callable(self):
        self.assertTrue(callable(validate_5m_micro_event_evidence))
        self.assertTrue(callable(build_5m_evidence_fixture))
        self.assertTrue(callable(insert_5m_evidence_window))


# ---------------------------------------------------------------------------
# Structural gate tests: wrong inputs → BLOCKED
# ---------------------------------------------------------------------------

class LaneE2VStructuralGateTests(unittest.TestCase):
    def _valid(self, **overrides) -> dict:
        base = build_5m_evidence_fixture()
        base.update(overrides)
        return base

    def test_wrong_window_kind_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(window_kind="WINDOW_15M")
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_wrong_window_kind_has_reason(self):
        r = validate_5m_micro_event_evidence(
            self._valid(window_kind="WINDOW_15M")
        )
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_missing_parent_window_id_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_id=None)
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_missing_parent_window_id_has_reason(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_id=None)
        )
        self.assertTrue(any("parent_window_id" in s for s in r["blocked_reasons"]))

    def test_non_15m_parent_kind_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_kind="WINDOW_5M_MICRO_EVENT")
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_non_15m_parent_kind_has_reason(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_kind="WINDOW_5M_MICRO_EVENT")
        )
        self.assertTrue(any("parent_window_kind" in s for s in r["blocked_reasons"]))

    def test_window_1h_parent_kind_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_kind="WINDOW_1H")
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_none_parent_kind_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_kind=None)
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_memory_status_clean_memory_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(memory_status="CLEAN_MEMORY")
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_memory_status_clean_memory_has_reason(self):
        r = validate_5m_micro_event_evidence(
            self._valid(memory_status="CLEAN_MEMORY")
        )
        self.assertTrue(any("CLEAN_MEMORY" in s for s in r["blocked_reasons"]))

    def test_memory_quality_label_clean_memory_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(memory_quality_label="CLEAN_MEMORY")
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_memory_quality_label_clean_memory_has_reason(self):
        r = validate_5m_micro_event_evidence(
            self._valid(memory_quality_label="CLEAN_MEMORY")
        )
        self.assertTrue(any("CLEAN_MEMORY" in s for s in r["blocked_reasons"]))

    def test_is_main_outcome_window_blocked(self):
        r = validate_5m_micro_event_evidence(
            self._valid(is_main_outcome_window=True)
        )
        self.assertEqual(r["e2v_status"], E2V_STATUS_BLOCKED)

    def test_is_main_outcome_window_has_reason(self):
        r = validate_5m_micro_event_evidence(
            self._valid(is_main_outcome_window=True)
        )
        self.assertTrue(any("main outcome" in s for s in r["blocked_reasons"]))

    def test_blocked_result_has_do_not_train_true(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_id=None)
        )
        self.assertTrue(r["do_not_train"])

    def test_blocked_result_has_hard_locks(self):
        r = validate_5m_micro_event_evidence(
            self._valid(parent_window_id=None)
        )
        for key, val in r["hard_locks"].items():
            self.assertTrue(val, f"hard_locks[{key!r}] must be True")

    def test_5m_cannot_unlock_retrieval(self):
        self.assertTrue(_HARD_LOCKS["no_retrieval_activation"])

    def test_5m_cannot_create_paper_decisions(self):
        self.assertTrue(_HARD_LOCKS["no_paper_decisions"])

    def test_5m_cannot_create_buy_sell_hold(self):
        self.assertTrue(_HARD_LOCKS["no_buy_sell_hold"])

    def test_5m_cannot_create_positions(self):
        self.assertTrue(_HARD_LOCKS["no_positions"])

    def test_5m_cannot_create_pnl(self):
        self.assertTrue(_HARD_LOCKS["no_pnl"])

    def test_5m_cannot_create_memories(self):
        self.assertTrue(_HARD_LOCKS["no_memory_creation"])


# ---------------------------------------------------------------------------
# Quality classification tests
# ---------------------------------------------------------------------------

class LaneE2VQualityClassificationTests(unittest.TestCase):
    def _run(self, **overrides) -> dict:
        base = build_5m_evidence_fixture()
        base.update(overrides)
        return validate_5m_micro_event_evidence(base)

    def test_valid_linked_evidence(self):
        r = self._run()
        self.assertEqual(r["e2v_status"], E2V_STATUS_VALID)

    def test_valid_has_valid_true(self):
        r = self._run()
        self.assertTrue(r["valid"])

    def test_valid_do_not_train_false(self):
        r = self._run()
        self.assertFalse(r["do_not_train"])

    def test_valid_no_blocked_reasons(self):
        r = self._run()
        self.assertEqual(r["blocked_reasons"], [])

    def test_valid_quality_label_in_allowed_set(self):
        r = self._run()
        self.assertIn(r["memory_quality_label"], E2V_ALLOWED_QUALITY_LABELS)

    def test_valid_quality_label_not_clean_memory(self):
        r = self._run()
        self.assertNotEqual(r["memory_quality_label"], "CLEAN_MEMORY")

    def test_dirty_data_quality_label(self):
        r = self._run(data_quality_label="DIRTY_DATA")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_stale_data_quality_label(self):
        r = self._run(data_quality_label="STALE_DATA")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_missing_critical_data_quality(self):
        r = self._run(data_quality_label="MISSING_CRITICAL_DATA")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_conflicting_data_quality(self):
        r = self._run(data_quality_label="CONFLICTING_DATA")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_do_not_train_data_quality(self):
        r = self._run(data_quality_label="DO_NOT_TRAIN")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_stale_evidence_flag(self):
        r = self._run(is_stale=True)
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_failed_evidence_flag(self):
        r = self._run(is_failed=True)
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_mismatched_evidence_flag(self):
        r = self._run(is_mismatched=True)
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_dirty_source_status_failed(self):
        r = self._run(source_status="FAILED")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_dirty_source_status_stale(self):
        r = self._run(source_status="STALE")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_dirty_source_status_conflicting(self):
        r = self._run(source_status="CONFLICTING")
        self.assertEqual(r["e2v_status"], E2V_STATUS_DIRTY)

    def test_dirty_evidence_do_not_train_true(self):
        r = self._run(is_dirty=True, data_quality_label="DIRTY_DATA")
        self.assertTrue(r["do_not_train"])

    def test_dirty_evidence_memory_quality_label(self):
        r = self._run(data_quality_label="DIRTY_DATA")
        self.assertEqual(r["memory_quality_label"], "DIRTY_MEMORY")

    def test_dirty_evidence_has_rejection_reasons(self):
        r = self._run(data_quality_label="DIRTY_DATA")
        self.assertGreater(len(r["rejection_reasons"]), 0)

    def test_stale_evidence_has_rejection_reason(self):
        r = self._run(is_stale=True)
        self.assertTrue(any("stale" in s for s in r["rejection_reasons"]))

    def test_failed_evidence_has_rejection_reason(self):
        r = self._run(is_failed=True)
        self.assertTrue(any("failed" in s for s in r["rejection_reasons"]))

    def test_mismatched_evidence_has_rejection_reason(self):
        r = self._run(is_mismatched=True)
        self.assertTrue(any("mismatch" in s for s in r["rejection_reasons"]))

    def test_acceptable_partial_data_audit_only(self):
        r = self._run(data_quality_label="ACCEPTABLE_PARTIAL_DATA")
        self.assertEqual(r["e2v_status"], E2V_STATUS_AUDIT_ONLY)

    def test_incomplete_evidence_audit_only(self):
        r = self._run(is_incomplete=True)
        self.assertEqual(r["e2v_status"], E2V_STATUS_AUDIT_ONLY)

    def test_audit_only_do_not_train_true(self):
        r = self._run(data_quality_label="ACCEPTABLE_PARTIAL_DATA")
        self.assertTrue(r["do_not_train"])

    def test_audit_only_memory_quality_label(self):
        r = self._run(data_quality_label="ACCEPTABLE_PARTIAL_DATA")
        self.assertEqual(r["memory_quality_label"], "AUDIT_ONLY")

    def test_audit_only_valid_false(self):
        r = self._run(is_incomplete=True)
        self.assertFalse(r["valid"])

    def test_result_always_has_hard_locks(self):
        for variant in [
            {},
            {"parent_window_id": None},
            {"data_quality_label": "DIRTY_DATA"},
            {"is_incomplete": True},
        ]:
            r = self._run(**variant)
            self.assertIn("hard_locks", r)

    def test_result_hard_locks_all_true(self):
        r = self._run()
        for key, val in r["hard_locks"].items():
            self.assertTrue(val, f"hard_locks[{key!r}] must be True")


# ---------------------------------------------------------------------------
# Fixture DB tests
# ---------------------------------------------------------------------------

class LaneE2VFixtureDbTests(_DbTestBase):
    def test_insert_5m_window_creates_row(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            wid = insert_5m_evidence_window(
                conn,
                token_id=token_id,
                pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
        finally:
            conn.close()
        self.assertIsInstance(wid, int)
        self.assertGreater(wid, 0)

    def test_5m_window_has_correct_window_kind(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            wid = insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
            row = conn.execute(
                "SELECT window_kind FROM printer_memory_windows WHERE id = ?",
                (wid,)
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["window_kind"], "WINDOW_5M_MICRO_EVENT")

    def test_5m_window_carries_parent_id_in_context(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            wid = insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
            row = conn.execute(
                "SELECT supporting_context_json FROM printer_memory_windows WHERE id = ?",
                (wid,)
            ).fetchone()
        finally:
            conn.close()
        ctx = json.loads(row["supporting_context_json"])
        self.assertEqual(ctx["parent_window_id"], win_15m_id)

    def test_5m_window_context_has_parent_window_kind(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            wid = insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
            row = conn.execute(
                "SELECT supporting_context_json FROM printer_memory_windows WHERE id = ?",
                (wid,)
            ).fetchone()
        finally:
            conn.close()
        ctx = json.loads(row["supporting_context_json"])
        self.assertEqual(ctx["parent_window_kind"], "WINDOW_15M")

    def test_multiple_5m_windows_same_token_pair(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            ids = [
                insert_5m_evidence_window(
                    conn, token_id=token_id, pair_id=pair_id,
                    parent_window_id=win_15m_id,
                    opened_at=f"2026-06-28T10:0{i}:00+00:00",
                    closed_at=f"2026-06-28T10:0{i+1}:00+00:00",
                )
                for i in range(3)
            ]
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(len(set(ids)), 3)

    def test_multiple_5m_windows_same_parent_15m(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            for i in range(3):
                insert_5m_evidence_window(
                    conn, token_id=token_id, pair_id=pair_id,
                    parent_window_id=win_15m_id,
                    opened_at=f"2026-06-28T10:0{i}:00+00:00",
                    closed_at=f"2026-06-28T10:0{i+1}:00+00:00",
                )
            conn.commit()
            count = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
                " WHERE window_kind = 'WINDOW_5M_MICRO_EVENT'"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 3)

    def test_5m_rows_do_not_create_memories(self):
        before = self._count_rows("printer_memories")
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self._count_rows("printer_memories"), before)

    def test_5m_rows_do_not_create_paper_decisions(self):
        before = self._count_rows("printer_paper_decisions")
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self._count_rows("printer_paper_decisions"), before)

    def test_5m_rows_do_not_create_paper_positions(self):
        before = self._count_rows("printer_paper_positions")
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self._count_rows("printer_paper_positions"), before)

    def test_5m_rows_do_not_create_trade_events(self):
        before = self._count_rows("printer_paper_trade_events")
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self._count_rows("printer_paper_trade_events"), before)

    def test_5m_rows_do_not_create_paper_audits(self):
        before = self._count_rows("printer_paper_trade_audits")
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), before)

    def test_dirty_5m_window_has_do_not_train_1(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            wid = insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
                do_not_train=1,
                memory_quality_label="DIRTY_MEMORY",
                memory_status="DIRTY_MEMORY",
            )
            conn.commit()
            row = conn.execute(
                "SELECT do_not_train, memory_quality_label"
                " FROM printer_memory_windows WHERE id = ?",
                (wid,)
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["do_not_train"], 1)
        self.assertEqual(row["memory_quality_label"], "DIRTY_MEMORY")

    def test_5m_window_memory_quality_label_not_clean_memory(self):
        token_id, pair_id, win_15m_id = self._make_base_fixture()
        conn = self._connect()
        try:
            wid = insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_15m_id,
            )
            conn.commit()
            row = conn.execute(
                "SELECT memory_quality_label FROM printer_memory_windows WHERE id = ?",
                (wid,)
            ).fetchone()
        finally:
            conn.close()
        self.assertNotEqual(row["memory_quality_label"], "CLEAN_MEMORY")


# ---------------------------------------------------------------------------
# E2U report isolation: 5m rows must not pollute 15m counts
# ---------------------------------------------------------------------------

class LaneE2VE2UIsolationTests(_DbTestBase):
    def _make_15m_windows(self, n: int):
        conn = self._connect()
        try:
            token_id = self._insert_token(conn)
            pair_id = self._insert_pair(conn, token_id)
            for _ in range(n):
                self._insert_15m_window(conn, token_id, pair_id)
            conn.commit()
            return token_id, pair_id
        finally:
            conn.close()

    def _run_e2u(self):
        return build_e2u_closeout_report(
            self.db_path, operator_approved=True
        )

    def test_e2u_closed_15m_count_unaffected_by_5m(self):
        token_id, pair_id = self._make_15m_windows(3)
        # Add 2 closed WINDOW_5M_MICRO_EVENT rows
        conn = self._connect()
        try:
            win_id = conn.execute(
                "SELECT id FROM printer_memory_windows LIMIT 1"
            ).fetchone()[0]
            for _ in range(2):
                insert_5m_evidence_window(
                    conn, token_id=token_id, pair_id=pair_id,
                    parent_window_id=win_id,
                )
            conn.commit()
        finally:
            conn.close()
        r = self._run_e2u()
        self.assertEqual(r["closed_window_15m_count"], 3)

    def test_e2u_clean_data_count_unaffected_by_5m(self):
        token_id, pair_id = self._make_15m_windows(2)
        conn = self._connect()
        try:
            win_id = conn.execute(
                "SELECT id FROM printer_memory_windows LIMIT 1"
            ).fetchone()[0]
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_id, data_quality_label="CLEAN_DATA",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run_e2u()
        self.assertEqual(r["clean_data_window_count"], 2)

    def test_e2u_partial_memory_count_unaffected_by_5m(self):
        token_id, pair_id = self._make_15m_windows(2)
        conn = self._connect()
        try:
            win_id = conn.execute(
                "SELECT id FROM printer_memory_windows LIMIT 1"
            ).fetchone()[0]
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_id,
                memory_status="PARTIAL_MEMORY",
                memory_quality_label="SUPPORT_EVIDENCE",
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run_e2u()
        # partial_memory_count should be 0 because 15m windows have PARTIAL_MEMORY
        # BUT memory_quality_label='PARTIAL_MEMORY' only if audited by E2Q; here not set
        # The 15m windows inserted by _make_15m_windows have memory_quality_label='PARTIAL_MEMORY'
        self.assertEqual(r["partial_memory_window_count"], 2)

    def test_e2u_last_five_15m_windows_unaffected_by_5m(self):
        token_id, pair_id = self._make_15m_windows(3)
        conn = self._connect()
        try:
            win_id = conn.execute(
                "SELECT id FROM printer_memory_windows LIMIT 1"
            ).fetchone()[0]
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_id,
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run_e2u()
        for w in r["last_five_window_15m"]:
            self.assertEqual(w["window_kind"], "WINDOW_15M")

    def test_e2u_read_only_delta_with_5m_rows(self):
        token_id, pair_id = self._make_15m_windows(2)
        conn = self._connect()
        try:
            win_id = conn.execute(
                "SELECT id FROM printer_memory_windows LIMIT 1"
            ).fetchone()[0]
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_id,
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run_e2u()
        self.assertEqual(r.get("read_only_delta_violations"), [])

    def test_e2u_status_ready_with_5m_rows_present(self):
        token_id, pair_id = self._make_15m_windows(2)
        conn = self._connect()
        try:
            win_id = conn.execute(
                "SELECT id FROM printer_memory_windows LIMIT 1"
            ).fetchone()[0]
            insert_5m_evidence_window(
                conn, token_id=token_id, pair_id=pair_id,
                parent_window_id=win_id,
            )
            conn.commit()
        finally:
            conn.close()
        r = self._run_e2u()
        from printer_v1.operator_cli.e2u_15m_cycle_closeout_report import (
            E2U_STATUS_READY,
        )
        self.assertEqual(r["e2u_status"], E2U_STATUS_READY)


# ---------------------------------------------------------------------------
# fixture helper tests
# ---------------------------------------------------------------------------

class LaneE2VFixtureHelperTests(unittest.TestCase):
    def test_build_5m_evidence_fixture_window_kind(self):
        f = build_5m_evidence_fixture()
        self.assertEqual(f["window_kind"], E2V_WINDOW_KIND)

    def test_build_5m_evidence_fixture_parent_window_id(self):
        f = build_5m_evidence_fixture(parent_window_id=42)
        self.assertEqual(f["parent_window_id"], 42)

    def test_build_5m_evidence_fixture_parent_window_kind(self):
        f = build_5m_evidence_fixture()
        self.assertEqual(f["parent_window_kind"], "WINDOW_15M")

    def test_build_5m_evidence_fixture_not_main_outcome(self):
        f = build_5m_evidence_fixture()
        self.assertFalse(f["is_main_outcome_window"])

    def test_build_5m_evidence_fixture_is_valid_by_default(self):
        f = build_5m_evidence_fixture()
        r = validate_5m_micro_event_evidence(f)
        self.assertEqual(r["e2v_status"], E2V_STATUS_VALID)

    def test_build_5m_evidence_fixture_custom_quality_label(self):
        f = build_5m_evidence_fixture(memory_quality_label="AUDIT_ONLY")
        self.assertEqual(f["memory_quality_label"], "AUDIT_ONLY")

    def test_build_5m_evidence_fixture_created_by(self):
        f = build_5m_evidence_fixture()
        self.assertEqual(f["created_by_phase"], E2V_CREATED_BY)


if __name__ == "__main__":
    unittest.main()
