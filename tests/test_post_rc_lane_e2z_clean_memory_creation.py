"""
Post-Lane 10 Lane E2Z -- Clean Memory Creation Boundary (Lane E closeout)

Five boundary proofs:
1. E2Y set gate must pass (set_gate_passed=True + window_id in candidate set)
2. valid passed E2Y candidate creates one clean printer_episodes row
3. invalid/5m/dirty candidate is blocked even with a valid E2Y report
4. duplicate run is idempotent
5. locked tables do not change
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
from printer_v1.operator_cli.e2z_clean_memory_creation import (
    E2Z_STATUS_ALREADY_EXISTS,
    E2Z_STATUS_BLOCKED,
    E2Z_STATUS_CREATED,
    _HARD_LOCKS,
    create_clean_memory_from_window,
)


_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR = "E2ZTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_NOW = "2026-06-28T10:00:00+00:00"

# E2Q context that passes all gates
_CLEAN_CTX = json.dumps({
    "snapshot_id": 99,
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

    def _insert_eligible_window(
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
        supporting_context_json: str = _CLEAN_CTX,
    ) -> int:
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, opened_at, closed_at,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, created_by_phase, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'lane_e2o', ?, ?)
            """,
            (
                token_id, pair_id, window_kind, _NOW, _NOW,
                memory_status, data_quality_label, do_not_train,
                window_status, memory_quality_label,
                supporting_context_json, _NOW, _NOW,
            ),
        )
        return int(cur.lastrowid)

    def _make_eligible(self) -> tuple[int, int, int]:
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid = self._insert_eligible_window(conn, tid, pid)
            conn.commit()
        finally:
            conn.close()
        return tid, pid, wid

    def _make_e2y_report(self, *window_ids: int | None) -> dict:
        """Build a minimal passed E2Y report containing the given window IDs."""
        return {
            "set_gate_passed": True,
            "candidate_set_summary": {
                "candidate_ids": [w for w in window_ids if w is not None],
            },
        }

    def _run(self, window_id, *, operator_approved=True, e2y_report=None):
        if e2y_report is None:
            e2y_report = self._make_e2y_report(window_id)
        return create_clean_memory_from_window(
            self.db_path, window_id,
            operator_approved=operator_approved,
            e2y_report=e2y_report,
        )


# ============================================================
# 1. Approval required
# ============================================================

class LaneE2ZApprovalTests(_Base):
    def test_blocked_when_not_approved(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid, operator_approved=False)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_has_reasons(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid, operator_approved=False)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_blocked_no_episode_created(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_episodes")
        self._run(wid, operator_approved=False)
        self.assertEqual(self._count("printer_episodes"), before)

    def test_blocked_when_window_id_none(self):
        r = create_clean_memory_from_window(
            self.db_path, None, operator_approved=True,
        )
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_when_db_path_none(self):
        r = create_clean_memory_from_window(
            None, 1, operator_approved=True,
        )
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_when_db_missing(self):
        r = create_clean_memory_from_window(
            pathlib.Path(self._tmp.name) / "no.db",
            1, operator_approved=True,
        )
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_hard_locks_all_true_on_blocked(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid, operator_approved=False)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v, f"hard_locks[{k!r}] must be True")

    def test_retrieval_not_activated_on_blocked(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid, operator_approved=False)
        self.assertFalse(r["retrieval_activated"])

    def test_buy_not_enabled_on_blocked(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid, operator_approved=False)
        self.assertFalse(r["buy_enabled"])


# ============================================================
# 2. Valid E2Y candidate can create clean memory
# ============================================================

class LaneE2ZCreationTests(_Base):
    def test_valid_candidate_creates_episode(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_CREATED)

    def test_episode_id_returned(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertIsInstance(r["episode_id"], int)
        self.assertGreater(r["episode_id"], 0)

    def test_created_true_on_success(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertTrue(r["created"])

    def test_episode_row_exists_in_db(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT * FROM printer_episodes WHERE id = ?",
                (r["episode_id"],)
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)

    def test_episode_has_clean_memory_status(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT memory_status FROM printer_episodes WHERE id = ?",
                (r["episode_id"],)
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["memory_status"], "CLEAN_MEMORY")

    def test_episode_links_to_window(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT memory_window_id FROM printer_episodes WHERE id = ?",
                (r["episode_id"],)
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["memory_window_id"], wid)

    def test_episode_has_clean_data_quality(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT data_quality_label FROM printer_episodes WHERE id = ?",
                (r["episode_id"],)
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")

    def test_episode_do_not_train_zero(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT do_not_train FROM printer_episodes WHERE id = ?",
                (r["episode_id"],)
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["do_not_train"], 0)

    def test_hard_locks_all_true_on_created(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        for k, v in r["hard_locks"].items():
            self.assertTrue(v)

    def test_retrieval_not_activated_on_created(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertFalse(r["retrieval_activated"])

    def test_buy_not_enabled_on_created(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertFalse(r["buy_enabled"])


# ============================================================
# 3. Invalid / 5m / dirty candidates are blocked
# ============================================================

class LaneE2ZInvalidCandidateTests(_Base):
    def _make_window(self, **overrides) -> int:
        conn = self._connect()
        try:
            tid = self._insert_token(conn)
            pid = self._insert_pair(conn, tid)
            wid = self._insert_eligible_window(conn, tid, pid, **overrides)
            conn.commit()
        finally:
            conn.close()
        return wid

    def test_5m_window_blocked(self):
        wid = self._make_window(window_kind="WINDOW_5M_MICRO_EVENT")
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_open_window_blocked(self):
        wid = self._make_window(window_status="WINDOW_OPEN")
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_dirty_data_quality_blocked(self):
        wid = self._make_window(
            data_quality_label="DIRTY_DATA",
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
        )
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_do_not_train_flag_blocked(self):
        wid = self._make_window(do_not_train=1)
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_dirty_memory_status_blocked(self):
        wid = self._make_window(
            memory_status="DIRTY_MEMORY",
            memory_quality_label="DIRTY_MEMORY",
        )
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_audit_only_memory_status_blocked(self):
        wid = self._make_window(
            memory_status="AUDIT_ONLY",
            memory_quality_label="AUDIT_ONLY",
        )
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_legacy_clean_memory_label_blocked(self):
        # window already labeled CLEAN_MEMORY on the window row is blocked
        # (memory_status check enforces PARTIAL_MEMORY)
        wid = self._make_window(
            memory_status="CLEAN_MEMORY",
            memory_quality_label="CLEAN_MEMORY",
        )
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_non_e2q_audited_blocked(self):
        ctx_no_audit = json.dumps({"snapshot_id": 99}, sort_keys=True)
        wid = self._make_window(supporting_context_json=ctx_no_audit)
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_no_snapshot_link_blocked(self):
        ctx_no_snap = json.dumps({"e2q_audited": True}, sort_keys=True)
        wid = self._make_window(supporting_context_json=ctx_no_snap)
        r = self._run(wid)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_nonexistent_window_id_blocked(self):
        r = self._run(99999)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_has_reasons(self):
        wid = self._make_window(window_kind="WINDOW_5M_MICRO_EVENT")
        r = self._run(wid)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_blocked_no_episode_created(self):
        wid = self._make_window(window_kind="WINDOW_5M_MICRO_EVENT")
        before = self._count("printer_episodes")
        self._run(wid)
        self.assertEqual(self._count("printer_episodes"), before)


# ============================================================
# 4. Duplicate run is idempotent
# ============================================================

class LaneE2ZIdempotencyTests(_Base):
    def test_second_call_returns_already_exists(self):
        _, _, wid = self._make_eligible()
        self._run(wid)
        r2 = self._run(wid)
        self.assertEqual(r2["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)

    def test_second_call_does_not_create_extra_episode(self):
        _, _, wid = self._make_eligible()
        self._run(wid)
        before = self._count("printer_episodes")
        self._run(wid)
        self.assertEqual(self._count("printer_episodes"), before)

    def test_second_call_returns_same_episode_id(self):
        _, _, wid = self._make_eligible()
        r1 = self._run(wid)
        r2 = self._run(wid)
        self.assertEqual(r2["episode_id"], r1["episode_id"])

    def test_third_call_still_already_exists(self):
        _, _, wid = self._make_eligible()
        self._run(wid)
        self._run(wid)
        r3 = self._run(wid)
        self.assertEqual(r3["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
        self.assertEqual(self._count("printer_episodes"), 1)

    def test_idempotent_call_created_false(self):
        _, _, wid = self._make_eligible()
        self._run(wid)
        r2 = self._run(wid)
        self.assertFalse(r2["created"])

    def test_idempotent_hard_locks_still_true(self):
        _, _, wid = self._make_eligible()
        self._run(wid)
        r2 = self._run(wid)
        for k, v in r2["hard_locks"].items():
            self.assertTrue(v)


# ============================================================
# 5. Retrieval and paper tables do not change
# ============================================================

class LaneE2ZLockedTablesTests(_Base):
    def test_no_retrieval_queries_created(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_memory_retrieval_queries")
        self._run(wid)
        self.assertEqual(self._count("printer_memory_retrieval_queries"), before)

    def test_no_retrieval_results_created(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_memory_retrieval_results")
        self._run(wid)
        self.assertEqual(self._count("printer_memory_retrieval_results"), before)

    def test_no_paper_decisions_created(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_paper_decisions")
        self._run(wid)
        self.assertEqual(self._count("printer_paper_decisions"), before)

    def test_no_paper_positions_created(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_paper_positions")
        self._run(wid)
        self.assertEqual(self._count("printer_paper_positions"), before)

    def test_no_paper_trade_events_created(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_paper_trade_events")
        self._run(wid)
        self.assertEqual(self._count("printer_paper_trade_events"), before)

    def test_no_paper_trade_audits_created(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_paper_trade_audits")
        self._run(wid)
        self.assertEqual(self._count("printer_paper_trade_audits"), before)

    def test_paper_decisions_created_zero_in_result(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_positions_created_zero_in_result(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertEqual(r["positions_created"], 0)

    def test_pnl_created_zero_in_result(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertEqual(r["pnl_created"], 0)

    def test_retrieval_activated_false_in_result(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertFalse(r["retrieval_activated"])

    def test_buy_enabled_false_in_result(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertFalse(r["buy_enabled"])

    def test_sell_enabled_false_in_result(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertFalse(r["sell_enabled"])

    def test_hold_enabled_false_in_result(self):
        _, _, wid = self._make_eligible()
        r = self._run(wid)
        self.assertFalse(r["hold_enabled"])

    def test_no_window_row_mutated(self):
        """The printer_memory_windows row is not touched."""
        _, _, wid = self._make_eligible()
        conn = self._connect()
        try:
            before_updated = conn.execute(
                "SELECT updated_at FROM printer_memory_windows WHERE id = ?",
                (wid,)
            ).fetchone()["updated_at"]
        finally:
            conn.close()
        self._run(wid)
        conn = self._connect()
        try:
            after_updated = conn.execute(
                "SELECT updated_at FROM printer_memory_windows WHERE id = ?",
                (wid,)
            ).fetchone()["updated_at"]
        finally:
            conn.close()
        self.assertEqual(before_updated, after_updated)


# ============================================================
# E2Y set-gate boundary (new requirement)
# Proofs: 1 (set_gate_passed required) and 2 (window_id must be in candidate set)
# ============================================================

class LaneE2ZE2YGateTests(_Base):
    """E2Z must refuse to promote a window unless a passed E2Y report backs it."""

    def test_blocked_when_e2y_report_none(self):
        _, _, wid = self._make_eligible()
        r = create_clean_memory_from_window(
            self.db_path, wid, operator_approved=True, e2y_report=None,
        )
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_e2y_none_has_reason(self):
        _, _, wid = self._make_eligible()
        r = create_clean_memory_from_window(
            self.db_path, wid, operator_approved=True, e2y_report=None,
        )
        self.assertTrue(
            any("e2y_report" in reason for reason in r["blocked_reasons"]),
            msg=f"expected e2y_report reason in {r['blocked_reasons']}",
        )

    def test_blocked_when_set_gate_not_passed(self):
        _, _, wid = self._make_eligible()
        bad_report = self._make_e2y_report(wid)
        bad_report["set_gate_passed"] = False
        r = self._run(wid, e2y_report=bad_report)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_set_gate_false_has_reason(self):
        _, _, wid = self._make_eligible()
        bad_report = self._make_e2y_report(wid)
        bad_report["set_gate_passed"] = False
        r = self._run(wid, e2y_report=bad_report)
        self.assertTrue(
            any("set_gate_passed" in reason for reason in r["blocked_reasons"]),
            msg=f"expected set_gate_passed reason in {r['blocked_reasons']}",
        )

    def test_blocked_when_set_gate_missing(self):
        _, _, wid = self._make_eligible()
        bad_report = {"candidate_set_summary": {"candidate_ids": [wid]}}
        r = self._run(wid, e2y_report=bad_report)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_when_window_not_in_candidate_set(self):
        _, _, wid = self._make_eligible()
        # Report passes but does not include this window_id
        other_report = {
            "set_gate_passed": True,
            "candidate_set_summary": {"candidate_ids": [wid + 1000]},
        }
        r = self._run(wid, e2y_report=other_report)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_blocked_window_not_in_set_has_reason(self):
        _, _, wid = self._make_eligible()
        other_report = {
            "set_gate_passed": True,
            "candidate_set_summary": {"candidate_ids": [wid + 1000]},
        }
        r = self._run(wid, e2y_report=other_report)
        self.assertTrue(
            any("candidate set" in reason for reason in r["blocked_reasons"]),
            msg=f"expected candidate set reason in {r['blocked_reasons']}",
        )

    def test_blocked_when_candidate_ids_empty(self):
        _, _, wid = self._make_eligible()
        empty_report = {
            "set_gate_passed": True,
            "candidate_set_summary": {"candidate_ids": []},
        }
        r = self._run(wid, e2y_report=empty_report)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_BLOCKED)

    def test_no_episode_on_e2y_gate_block(self):
        _, _, wid = self._make_eligible()
        before = self._count("printer_episodes")
        create_clean_memory_from_window(
            self.db_path, wid, operator_approved=True, e2y_report=None,
        )
        self.assertEqual(self._count("printer_episodes"), before)

    def test_no_episode_when_window_not_in_set(self):
        _, _, wid = self._make_eligible()
        other_report = {
            "set_gate_passed": True,
            "candidate_set_summary": {"candidate_ids": [wid + 1000]},
        }
        before = self._count("printer_episodes")
        self._run(wid, e2y_report=other_report)
        self.assertEqual(self._count("printer_episodes"), before)

    def test_creates_episode_when_window_in_passed_set(self):
        _, _, wid = self._make_eligible()
        good_report = self._make_e2y_report(wid)
        r = self._run(wid, e2y_report=good_report)
        self.assertEqual(r["e2z_status"], E2Z_STATUS_CREATED)

    def test_e2y_gate_does_not_activate_retrieval(self):
        _, _, wid = self._make_eligible()
        r = create_clean_memory_from_window(
            self.db_path, wid, operator_approved=True, e2y_report=None,
        )
        self.assertFalse(r["retrieval_activated"])

    def test_e2y_gate_does_not_enable_buy(self):
        _, _, wid = self._make_eligible()
        r = create_clean_memory_from_window(
            self.db_path, wid, operator_approved=True, e2y_report=None,
        )
        self.assertFalse(r["buy_enabled"])

    def test_idempotent_with_same_e2y_report(self):
        _, _, wid = self._make_eligible()
        good_report = self._make_e2y_report(wid)
        self._run(wid, e2y_report=good_report)
        r2 = self._run(wid, e2y_report=good_report)
        self.assertEqual(r2["e2z_status"], E2Z_STATUS_ALREADY_EXISTS)
        self.assertEqual(self._count("printer_episodes"), 1)


if __name__ == "__main__":
    unittest.main()
