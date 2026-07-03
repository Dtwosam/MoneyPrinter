"""Lane V — Controlled Clean-Memory Retrieval Reporting (Audit-Only) tests.

Coverage proofs:
  1.  Clean memories included: 3 CLEAN episodes → clean_memory_count = 3
  2.  Dirty memories excluded from selected ids (DIRTY_MEMORY, PARTIAL_MEMORY)
  3.  DO_NOT_TRAIN episodes excluded from selected ids
  4.  5m support-only (WINDOW_5M_MICRO_EVENT) episodes excluded from selected ids
  5.  No retrieval rows created (printer_memory_retrieval_queries stays 0)
  6.  No paper decision rows created
  7.  No positions / PnL / trade rows created
  8.  No numeric scoring / ranking / confidence fields in report
  9.  Report is deterministic: same input → same output
 10.  token_id filter scopes selected_clean_memory_ids correctly
 11.  pair_id filter scopes selected_clean_memory_ids correctly
 12.  window_kind filter scopes selected_clean_memory_ids correctly
 13.  limit filter caps selected_clean_memory_ids
 14.  Group summary correct: grouped by (token_id, pair_id, window_kind)
 15.  Labels: SAME_PAIR when all same pair; SAME_TOKEN when all same token
 16.  RECENT_CLEAN_MEMORY label present when episodes exist
 17.  INSUFFICIENT_CLEAN_MEMORY label when < 5 episodes
 18.  CONFLICTING_OUTCOME_LABELS when episodes have different outcome labels
 19.  Financial locks all false / zero
 20.  Hard locks all True
 21.  db_path=None → LANE_V_REPORT_BLOCKED
 22.  db_path missing file → LANE_V_REPORT_BLOCKED
 23.  Zero clean memories is valid — not an error, just count = 0
 24.  excluded dirty count, DO_NOT_TRAIN count, support_only count reported
 25.  SAME_WINDOW_KIND label when all same window_kind
"""

from __future__ import annotations

import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_v_clean_memory_retrieval_report import (
    LABEL_CONFLICTING_OUTCOME_LABELS,
    LABEL_INSUFFICIENT_CLEAN_MEMORY,
    LABEL_RECENT_CLEAN_MEMORY,
    LABEL_SAME_PAIR,
    LABEL_SAME_TOKEN,
    LABEL_SAME_WINDOW_KIND,
    LANE_V_STATUS_BLOCKED,
    LANE_V_STATUS_READY,
    build_clean_memory_retrieval_report,
)


# ---------------------------------------------------------------------------
# Shared constants / helpers
# ---------------------------------------------------------------------------

_NOW = "2026-07-02T08:00:00+00:00"
_MINT_A = "LaneVTestMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_MINT_B = "LaneVTestMintBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_PAIR_A = "LaneVTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_B = "LaneVTestPairBBBBBBBBBBBBBBBBBBBBBBBBBBB"


class _VDbBase(unittest.TestCase):
    """Base class: creates a fully-migrated temp DB for each test."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)
        self._conn = sqlite3.connect(str(self.db_path))
        self._conn.row_factory = sqlite3.Row

    def tearDown(self):
        self._conn.close()
        self._tmp.cleanup()

    # --- row counters ---

    def _count(self, table: str) -> int:
        try:
            return int(self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0

    # --- insert helpers ---

    def _insert_token(self, mint: str = _MINT_A) -> int:
        return int(self._conn.execute(
            "INSERT INTO printer_tokens"
            " (token_mint, chain, symbol, name, first_seen_at, last_seen_at,"
            "  token_status, created_at, updated_at)"
            " VALUES (?, 'solana', 'T', 'T', ?, ?, 'TRACK_FAST', ?, ?)",
            (mint, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _insert_pair(self, token_id: int, pair_addr: str = _PAIR_A) -> int:
        return int(self._conn.execute(
            "INSERT INTO printer_pairs"
            " (token_id, pair_address, base_token_mint, first_seen_at, last_seen_at,"
            "  created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token_id, pair_addr, pair_addr, _NOW, _NOW, _NOW, _NOW),
        ).lastrowid)

    def _insert_window(
        self,
        token_id: int,
        pair_id: int,
        *,
        window_kind: str = "WINDOW_15M",
        memory_status: str = "PARTIAL_MEMORY",
    ) -> int:
        return int(self._conn.execute(
            "INSERT INTO printer_memory_windows"
            " (token_id, pair_id, window_kind, opened_at, closed_at,"
            "  memory_status, data_quality_label, do_not_train,"
            "  window_status, memory_quality_label,"
            "  supporting_context_json, created_by_phase, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'WINDOW_CLOSED', 'PARTIAL_MEMORY', '{}', 'test', ?, ?)",
            (token_id, pair_id, window_kind, _NOW, _NOW, memory_status, "CLEAN_DATA", _NOW, _NOW),
        ).lastrowid)

    def _insert_clean_episode(
        self,
        token_id: int,
        pair_id: int,
        window_id: int,
        *,
        window_kind: str = "WINDOW_15M",
        episode_outcome_label: str | None = None,
    ) -> int:
        return int(self._conn.execute(
            "INSERT INTO printer_episodes"
            " (memory_window_id, token_id, pair_id,"
            "  episode_kind, episode_status,"
            "  memory_status, data_quality_label, do_not_train,"
            "  window_kind, memory_quality_label,"
            "  episode_outcome_label,"
            "  supporting_context_json, created_at, updated_at)"
            " VALUES (?, ?, ?, ?, 'COMPLETE', 'CLEAN_MEMORY', 'CLEAN_DATA', 0, ?, 'CLEAN_MEMORY', ?, '{}', ?, ?)",
            (
                window_id, token_id, pair_id,
                "WINDOW_15M_CLEAN_MEMORY",
                window_kind,
                episode_outcome_label,
                _NOW, _NOW,
            ),
        ).lastrowid)

    def _insert_dirty_episode(
        self,
        token_id: int,
        pair_id: int,
        window_id: int,
        *,
        memory_status: str = "DIRTY_MEMORY",
        data_quality_label: str = "DIRTY_DATA",
    ) -> int:
        return int(self._conn.execute(
            "INSERT INTO printer_episodes"
            " (memory_window_id, token_id, pair_id,"
            "  episode_kind, episode_status,"
            "  memory_status, data_quality_label, do_not_train,"
            "  window_kind, memory_quality_label,"
            "  supporting_context_json, created_at, updated_at)"
            " VALUES (?, ?, ?, 'WINDOW_15M_DIRTY', 'COMPLETE',"
            "         ?, ?, 0, 'WINDOW_15M', 'PARTIAL_MEMORY', '{}', ?, ?)",
            (window_id, token_id, pair_id, memory_status, data_quality_label, _NOW, _NOW),
        ).lastrowid)

    def _insert_do_not_train_episode(
        self,
        token_id: int,
        pair_id: int,
        window_id: int,
    ) -> int:
        return int(self._conn.execute(
            "INSERT INTO printer_episodes"
            " (memory_window_id, token_id, pair_id,"
            "  episode_kind, episode_status,"
            "  memory_status, data_quality_label, do_not_train,"
            "  window_kind, memory_quality_label,"
            "  supporting_context_json, created_at, updated_at)"
            " VALUES (?, ?, ?, 'WINDOW_15M_DO_NOT_TRAIN', 'COMPLETE',"
            "         'DO_NOT_TRAIN', 'MISSING_CRITICAL_DATA', 1, 'WINDOW_15M', 'PARTIAL_MEMORY', '{}', ?, ?)",
            (window_id, token_id, pair_id, _NOW, _NOW),
        ).lastrowid)

    def _insert_support_only_episode(
        self,
        token_id: int,
        pair_id: int,
        window_id: int,
    ) -> int:
        return int(self._conn.execute(
            "INSERT INTO printer_episodes"
            " (memory_window_id, token_id, pair_id,"
            "  episode_kind, episode_status,"
            "  memory_status, data_quality_label, do_not_train,"
            "  window_kind, memory_quality_label,"
            "  supporting_context_json, created_at, updated_at)"
            " VALUES (?, ?, ?, 'WINDOW_5M_MICRO_EVENT', 'COMPLETE',"
            "         'CLEAN_MEMORY', 'CLEAN_DATA', 0,"
            "         'WINDOW_5M_MICRO_EVENT', 'CLEAN_MEMORY', '{}', ?, ?)",
            (window_id, token_id, pair_id, _NOW, _NOW),
        ).lastrowid)

    def _report(self, **kwargs) -> dict:
        self._conn.commit()
        return build_clean_memory_retrieval_report(self.db_path, **kwargs)

    # --- standard 3-clean-episode fixture ---
    def _make_three_clean(self) -> tuple[int, int, list[int], list[int]]:
        """Insert 1 token, 1 pair, 3 windows, 3 clean episodes. Returns (tid, pid, wids, eids)."""
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        wids, eids = [], []
        for _ in range(3):
            wid = self._insert_window(tid, pid)
            eid = self._insert_clean_episode(tid, pid, wid)
            wids.append(wid)
            eids.append(eid)
        return tid, pid, wids, eids

    # --- 6-clean + 1-dirty fixture ---
    def _make_six_clean_one_dirty(self) -> tuple[int, int, list[int], list[int], int]:
        """Returns (tid, pid, clean_eids, clean_wids, dirty_eid)."""
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        clean_eids, clean_wids = [], []
        for _ in range(6):
            wid = self._insert_window(tid, pid)
            eid = self._insert_clean_episode(tid, pid, wid)
            clean_wids.append(wid)
            clean_eids.append(eid)
        dirty_wid = self._insert_window(tid, pid)
        dirty_eid = self._insert_dirty_episode(tid, pid, dirty_wid)
        return tid, pid, clean_eids, clean_wids, dirty_eid


# ===========================================================================
# Proof 1 — Clean memories included in report
# ===========================================================================

class LaneVCleanMemoryIncludedTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._tid, self._pid, self._wids, self._eids = self._make_three_clean()
        self._result = self._report()

    def test_status_is_ready(self):
        self.assertEqual(self._result["lane_v_status"], LANE_V_STATUS_READY)

    def test_clean_memory_count_is_3(self):
        self.assertEqual(self._result["clean_memory_count"], 3)

    def test_selected_clean_memory_ids_length_is_3(self):
        self.assertEqual(len(self._result["selected_clean_memory_ids"]), 3)

    def test_selected_clean_memory_ids_contains_all_episode_ids(self):
        self.assertEqual(
            sorted(self._result["selected_clean_memory_ids"]),
            sorted(self._eids),
        )

    def test_selected_window_ids_contains_all_window_ids(self):
        self.assertEqual(
            sorted(self._result["selected_window_ids"]),
            sorted(self._wids),
        )

    def test_order_is_id_desc(self):
        ids = self._result["selected_clean_memory_ids"]
        self.assertEqual(ids, sorted(ids, reverse=True))


# ===========================================================================
# Proof 2 — Dirty memories excluded
# ===========================================================================

class LaneVDirtyExcludedTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        wid_clean = self._insert_window(tid, pid)
        eid_clean = self._insert_clean_episode(tid, pid, wid_clean)
        wid_dirty = self._insert_window(tid, pid)
        self._dirty_eid = self._insert_dirty_episode(tid, pid, wid_dirty)
        wid_partial = self._insert_window(tid, pid)
        self._partial_eid = self._insert_dirty_episode(
            tid, pid, wid_partial,
            memory_status="PARTIAL_MEMORY", data_quality_label="MISSING_CRITICAL_DATA",
        )
        self._clean_eid = eid_clean
        self._result = self._report()

    def test_dirty_not_in_selected_ids(self):
        self.assertNotIn(self._dirty_eid, self._result["selected_clean_memory_ids"])

    def test_partial_not_in_selected_ids(self):
        self.assertNotIn(self._partial_eid, self._result["selected_clean_memory_ids"])

    def test_clean_still_in_selected_ids(self):
        self.assertIn(self._clean_eid, self._result["selected_clean_memory_ids"])

    def test_dirty_memory_excluded_count_is_2(self):
        self.assertEqual(self._result["dirty_memory_excluded_count"], 2)

    def test_clean_memory_count_is_1(self):
        self.assertEqual(self._result["clean_memory_count"], 1)


# ===========================================================================
# Proof 3 — DO_NOT_TRAIN excluded
# ===========================================================================

class LaneVDoNotTrainExcludedTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        wid_clean = self._insert_window(tid, pid)
        self._clean_eid = self._insert_clean_episode(tid, pid, wid_clean)
        wid_dnt = self._insert_window(tid, pid)
        self._dnt_eid = self._insert_do_not_train_episode(tid, pid, wid_dnt)
        self._result = self._report()

    def test_do_not_train_not_in_selected_ids(self):
        self.assertNotIn(self._dnt_eid, self._result["selected_clean_memory_ids"])

    def test_clean_still_selected(self):
        self.assertIn(self._clean_eid, self._result["selected_clean_memory_ids"])

    def test_do_not_train_excluded_count_is_1(self):
        self.assertEqual(self._result["do_not_train_excluded_count"], 1)

    def test_clean_count_is_1(self):
        self.assertEqual(self._result["clean_memory_count"], 1)


# ===========================================================================
# Proof 4 — 5m support-only excluded
# ===========================================================================

class LaneVSupportOnlyExcludedTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        wid_clean = self._insert_window(tid, pid)
        self._clean_eid = self._insert_clean_episode(tid, pid, wid_clean)
        wid_5m = self._insert_window(tid, pid, window_kind="WINDOW_5M_MICRO_EVENT")
        self._support_eid = self._insert_support_only_episode(tid, pid, wid_5m)
        self._result = self._report()

    def test_support_only_not_in_selected_ids(self):
        self.assertNotIn(self._support_eid, self._result["selected_clean_memory_ids"])

    def test_clean_15m_still_selected(self):
        self.assertIn(self._clean_eid, self._result["selected_clean_memory_ids"])

    def test_support_only_excluded_count_is_1(self):
        self.assertEqual(self._result["support_only_excluded_count"], 1)

    def test_clean_count_is_1(self):
        self.assertEqual(self._result["clean_memory_count"], 1)


# ===========================================================================
# Proof 5 — No retrieval rows created
# ===========================================================================

class LaneVNoRetrievalRowsTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._before_queries = self._count("printer_memory_retrieval_queries")
        self._before_matches = self._count("printer_memory_retrieval_matches")
        tid, pid, _, _ = self._make_three_clean()
        self._result = self._report()

    def test_retrieval_queries_count_unchanged(self):
        after = self._count("printer_memory_retrieval_queries")
        self.assertEqual(after, self._before_queries)

    def test_retrieval_matches_count_unchanged(self):
        after = self._count("printer_memory_retrieval_matches")
        self.assertEqual(after, self._before_matches)

    def test_retrieval_activation_is_false(self):
        self.assertFalse(self._result["retrieval_activation"])

    def test_retrieval_queries_before_is_zero(self):
        self.assertEqual(self._before_queries, 0)


# ===========================================================================
# Proof 6 — No paper decision rows created
# ===========================================================================

class LaneVNoPaperDecisionsTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._before_decisions = self._count("printer_paper_decisions")
        self._make_three_clean()
        self._result = self._report()

    def test_paper_decisions_count_unchanged(self):
        after = self._count("printer_paper_decisions")
        self.assertEqual(after, self._before_decisions)

    def test_paper_decisions_created_field_is_zero(self):
        self.assertEqual(self._result["paper_decisions_created"], 0)

    def test_buy_enabled_is_false(self):
        self.assertFalse(self._result["buy_enabled"])

    def test_sell_enabled_is_false(self):
        self.assertFalse(self._result["sell_enabled"])

    def test_hold_enabled_is_false(self):
        self.assertFalse(self._result["hold_enabled"])


# ===========================================================================
# Proof 7 — No positions / PnL / trade rows created
# ===========================================================================

class LaneVNoPositionsOrPnlTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._before_positions = self._count("printer_paper_positions")
        self._before_trade_events = self._count("printer_paper_trade_events")
        self._before_audits = self._count("printer_paper_trade_audits")
        self._make_three_clean()
        self._result = self._report()

    def test_paper_positions_count_unchanged(self):
        after = self._count("printer_paper_positions")
        self.assertEqual(after, self._before_positions)

    def test_paper_trade_events_count_unchanged(self):
        after = self._count("printer_paper_trade_events")
        self.assertEqual(after, self._before_trade_events)

    def test_paper_trade_audits_count_unchanged(self):
        after = self._count("printer_paper_trade_audits")
        self.assertEqual(after, self._before_audits)

    def test_positions_created_field_is_zero(self):
        self.assertEqual(self._result["positions_created"], 0)

    def test_pnl_created_field_is_zero(self):
        self.assertEqual(self._result["pnl_created"], 0)


# ===========================================================================
# Proof 8 — No numeric scoring / ranking / confidence fields in report
# ===========================================================================

class LaneVNoNumericScoringTests(_VDbBase):
    _FORBIDDEN_KEYS = {
        "score", "rank", "ranking", "confidence", "similarity_score",
        "weighted_score", "embedding", "vector", "cosine_distance",
        "probability", "certainty",
    }

    def setUp(self):
        super().setUp()
        self._make_three_clean()
        self._result = self._report()

    def test_no_score_key_in_report(self):
        self.assertNotIn("score", self._result)

    def test_no_rank_key_in_report(self):
        self.assertNotIn("rank", self._result)

    def test_no_confidence_key_in_report(self):
        self.assertNotIn("confidence", self._result)

    def test_no_similarity_score_key_in_report(self):
        self.assertNotIn("similarity_score", self._result)

    def test_no_embedding_key_in_report(self):
        self.assertNotIn("embedding", self._result)

    def test_no_vector_key_in_report(self):
        self.assertNotIn("vector", self._result)

    def test_no_forbidden_keys_in_report(self):
        for key in self._FORBIDDEN_KEYS:
            self.assertNotIn(key, self._result, f"unexpected scoring key: {key}")

    def test_no_scoring_ranking_confidence_in_hard_locks(self):
        locks = self._result.get("hard_locks", {})
        self.assertTrue(locks.get("no_scoring_ranking_confidence"))


# ===========================================================================
# Proof 9 — Report is deterministic
# ===========================================================================

class LaneVDeterminismTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._make_three_clean()
        self._conn.commit()
        self._r1 = build_clean_memory_retrieval_report(self.db_path)
        self._r2 = build_clean_memory_retrieval_report(self.db_path)

    def test_clean_memory_count_same_both_runs(self):
        self.assertEqual(self._r1["clean_memory_count"], self._r2["clean_memory_count"])

    def test_selected_ids_same_both_runs(self):
        self.assertEqual(
            self._r1["selected_clean_memory_ids"],
            self._r2["selected_clean_memory_ids"],
        )

    def test_labels_same_both_runs(self):
        self.assertEqual(self._r1["report_labels"], self._r2["report_labels"])

    def test_group_summary_same_both_runs(self):
        self.assertEqual(self._r1["group_summary"], self._r2["group_summary"])


# ===========================================================================
# Proof 10 — token_id filter
# ===========================================================================

class LaneVTokenIdFilterTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._tid_a = self._insert_token(_MINT_A)
        self._pid_a = self._insert_pair(self._tid_a, _PAIR_A)
        self._tid_b = self._insert_token(_MINT_B)
        self._pid_b = self._insert_pair(self._tid_b, _PAIR_B)
        # 2 clean episodes for token A, 3 for token B
        self._a_eids = []
        self._b_eids = []
        for _ in range(2):
            wid = self._insert_window(self._tid_a, self._pid_a)
            self._a_eids.append(self._insert_clean_episode(self._tid_a, self._pid_a, wid))
        for _ in range(3):
            wid = self._insert_window(self._tid_b, self._pid_b)
            self._b_eids.append(self._insert_clean_episode(self._tid_b, self._pid_b, wid))
        self._conn.commit()

    def test_filter_token_a_returns_2(self):
        r = build_clean_memory_retrieval_report(self.db_path, token_id=self._tid_a)
        self.assertEqual(r["clean_memory_count"], 2)

    def test_filter_token_b_returns_3(self):
        r = build_clean_memory_retrieval_report(self.db_path, token_id=self._tid_b)
        self.assertEqual(r["clean_memory_count"], 3)

    def test_filter_token_a_ids_are_only_a(self):
        r = build_clean_memory_retrieval_report(self.db_path, token_id=self._tid_a)
        self.assertEqual(sorted(r["selected_clean_memory_ids"]), sorted(self._a_eids))

    def test_no_filter_returns_all_5(self):
        r = build_clean_memory_retrieval_report(self.db_path)
        self.assertEqual(r["clean_memory_count"], 5)

    def test_filter_stores_token_id_in_filters_applied(self):
        r = build_clean_memory_retrieval_report(self.db_path, token_id=self._tid_a)
        self.assertEqual(r["filters_applied"]["token_id"], self._tid_a)


# ===========================================================================
# Proof 11 — pair_id filter
# ===========================================================================

class LaneVPairIdFilterTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        self._pid_a = self._insert_pair(tid, _PAIR_A)
        self._pid_b = self._insert_pair(tid, _PAIR_B)
        self._a_eids = []
        self._b_eids = []
        for _ in range(2):
            wid = self._insert_window(tid, self._pid_a)
            self._a_eids.append(self._insert_clean_episode(tid, self._pid_a, wid))
        for _ in range(4):
            wid = self._insert_window(tid, self._pid_b)
            self._b_eids.append(self._insert_clean_episode(tid, self._pid_b, wid))
        self._conn.commit()

    def test_filter_pair_a_returns_2(self):
        r = build_clean_memory_retrieval_report(self.db_path, pair_id=self._pid_a)
        self.assertEqual(r["clean_memory_count"], 2)

    def test_filter_pair_b_returns_4(self):
        r = build_clean_memory_retrieval_report(self.db_path, pair_id=self._pid_b)
        self.assertEqual(r["clean_memory_count"], 4)

    def test_filter_pair_a_ids_match(self):
        r = build_clean_memory_retrieval_report(self.db_path, pair_id=self._pid_a)
        self.assertEqual(sorted(r["selected_clean_memory_ids"]), sorted(self._a_eids))

    def test_no_filter_returns_all_6(self):
        r = build_clean_memory_retrieval_report(self.db_path)
        self.assertEqual(r["clean_memory_count"], 6)


# ===========================================================================
# Proof 12 — window_kind filter
# ===========================================================================

class LaneVWindowKindFilterTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        self._15m_eids = []
        for _ in range(3):
            wid = self._insert_window(tid, pid, window_kind="WINDOW_15M")
            self._15m_eids.append(
                self._insert_clean_episode(tid, pid, wid, window_kind="WINDOW_15M")
            )
        self._conn.commit()

    def test_filter_window_15m_returns_3(self):
        r = build_clean_memory_retrieval_report(self.db_path, window_kind="WINDOW_15M")
        self.assertEqual(r["clean_memory_count"], 3)

    def test_filter_window_15m_ids_match(self):
        r = build_clean_memory_retrieval_report(self.db_path, window_kind="WINDOW_15M")
        self.assertEqual(sorted(r["selected_clean_memory_ids"]), sorted(self._15m_eids))

    def test_filter_nonexistent_window_kind_returns_0(self):
        r = build_clean_memory_retrieval_report(self.db_path, window_kind="WINDOW_1H")
        self.assertEqual(r["clean_memory_count"], 0)


# ===========================================================================
# Proof 13 — limit filter
# ===========================================================================

class LaneVLimitFilterTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._tid, self._pid, _, self._eids = self._make_three_clean()
        self._conn.commit()

    def test_limit_1_returns_1_result(self):
        r = build_clean_memory_retrieval_report(self.db_path, limit=1)
        self.assertEqual(r["clean_memory_count"], 1)
        self.assertEqual(len(r["selected_clean_memory_ids"]), 1)

    def test_limit_2_returns_2_results(self):
        r = build_clean_memory_retrieval_report(self.db_path, limit=2)
        self.assertEqual(r["clean_memory_count"], 2)

    def test_limit_1_returns_highest_id(self):
        r = build_clean_memory_retrieval_report(self.db_path, limit=1)
        self.assertEqual(r["selected_clean_memory_ids"][0], max(self._eids))

    def test_limit_larger_than_count_returns_all(self):
        r = build_clean_memory_retrieval_report(self.db_path, limit=100)
        self.assertEqual(r["clean_memory_count"], 3)


# ===========================================================================
# Proof 14 — Group summary
# ===========================================================================

class LaneVGroupSummaryTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid_a = self._insert_token(_MINT_A)
        pid_a = self._insert_pair(tid_a, _PAIR_A)
        tid_b = self._insert_token(_MINT_B)
        pid_b = self._insert_pair(tid_b, _PAIR_B)
        # 2 episodes on group A, 3 on group B
        for _ in range(2):
            wid = self._insert_window(tid_a, pid_a)
            self._insert_clean_episode(tid_a, pid_a, wid)
        for _ in range(3):
            wid = self._insert_window(tid_b, pid_b)
            self._insert_clean_episode(tid_b, pid_b, wid)
        self._result = self._report()

    def test_group_summary_has_2_groups(self):
        self.assertEqual(len(self._result["group_summary"]), 2)

    def test_groups_have_correct_counts(self):
        counts = sorted(g["count"] for g in self._result["group_summary"])
        self.assertEqual(counts, [2, 3])

    def test_each_group_has_episode_ids(self):
        for g in self._result["group_summary"]:
            self.assertIsInstance(g["episode_ids"], list)
            self.assertGreater(len(g["episode_ids"]), 0)

    def test_group_keys_present(self):
        for g in self._result["group_summary"]:
            self.assertIn("token_id", g)
            self.assertIn("pair_id", g)
            self.assertIn("window_kind", g)


# ===========================================================================
# Proof 15 — SAME_PAIR / SAME_TOKEN labels
# ===========================================================================

class LaneVSamePairTokenLabelTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        for _ in range(2):
            wid = self._insert_window(tid, pid)
            self._insert_clean_episode(tid, pid, wid)
        self._result = self._report()

    def test_same_pair_label_present(self):
        self.assertIn(LABEL_SAME_PAIR, self._result["report_labels"])

    def test_same_token_label_present(self):
        self.assertIn(LABEL_SAME_TOKEN, self._result["report_labels"])


class LaneVMultiPairNoSamePairLabelTests(_VDbBase):
    """When episodes span 2 pairs, SAME_PAIR should NOT appear."""

    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid_a = self._insert_pair(tid, _PAIR_A)
        pid_b = self._insert_pair(tid, _PAIR_B)
        wid_a = self._insert_window(tid, pid_a)
        wid_b = self._insert_window(tid, pid_b)
        self._insert_clean_episode(tid, pid_a, wid_a)
        self._insert_clean_episode(tid, pid_b, wid_b)
        self._result = self._report()

    def test_same_pair_label_absent_when_multi_pair(self):
        self.assertNotIn(LABEL_SAME_PAIR, self._result["report_labels"])

    def test_same_token_label_present_when_same_token(self):
        self.assertIn(LABEL_SAME_TOKEN, self._result["report_labels"])


# ===========================================================================
# Proof 16 — RECENT_CLEAN_MEMORY label
# ===========================================================================

class LaneVRecentCleanMemoryLabelTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._make_three_clean()
        self._result = self._report()

    def test_recent_clean_memory_label_present(self):
        self.assertIn(LABEL_RECENT_CLEAN_MEMORY, self._result["report_labels"])


class LaneVNoRecentLabelWhenEmptyTests(_VDbBase):
    def test_no_recent_label_on_empty_db(self):
        r = self._report()
        self.assertNotIn(LABEL_RECENT_CLEAN_MEMORY, r["report_labels"])

    def test_clean_count_is_zero_on_empty_db(self):
        r = self._report()
        self.assertEqual(r["clean_memory_count"], 0)


# ===========================================================================
# Proof 17 — INSUFFICIENT_CLEAN_MEMORY label (< 5)
# ===========================================================================

class LaneVInsufficientLabelTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._make_three_clean()
        self._result = self._report()

    def test_insufficient_label_present_when_3(self):
        self.assertIn(LABEL_INSUFFICIENT_CLEAN_MEMORY, self._result["report_labels"])


class LaneVNoInsufficientLabelWhenSixTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        for _ in range(6):
            wid = self._insert_window(tid, pid)
            self._insert_clean_episode(tid, pid, wid)
        self._result = self._report()

    def test_insufficient_label_absent_when_6(self):
        self.assertNotIn(LABEL_INSUFFICIENT_CLEAN_MEMORY, self._result["report_labels"])

    def test_clean_memory_count_is_6(self):
        self.assertEqual(self._result["clean_memory_count"], 6)


# ===========================================================================
# Proof 18 — CONFLICTING_OUTCOME_LABELS
# ===========================================================================

class LaneVConflictingOutcomeLabelsTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        wid1 = self._insert_window(tid, pid)
        self._insert_clean_episode(tid, pid, wid1, episode_outcome_label="OUTCOME_A")
        wid2 = self._insert_window(tid, pid)
        self._insert_clean_episode(tid, pid, wid2, episode_outcome_label="OUTCOME_B")
        self._result = self._report()

    def test_conflicting_outcome_labels_present(self):
        self.assertIn(LABEL_CONFLICTING_OUTCOME_LABELS, self._result["report_labels"])


class LaneVNoConflictingOutcomeLabelsTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        for _ in range(2):
            wid = self._insert_window(tid, pid)
            self._insert_clean_episode(tid, pid, wid, episode_outcome_label="OUTCOME_A")
        self._result = self._report()

    def test_no_conflicting_label_when_same_outcome(self):
        self.assertNotIn(LABEL_CONFLICTING_OUTCOME_LABELS, self._result["report_labels"])


# ===========================================================================
# Proof 19 — Financial locks all false / zero
# ===========================================================================

class LaneVFinancialLocksTests(_VDbBase):
    def setUp(self):
        super().setUp()
        self._make_three_clean()
        self._result = self._report()

    def test_buy_enabled_false(self):
        self.assertFalse(self._result["buy_enabled"])

    def test_sell_enabled_false(self):
        self.assertFalse(self._result["sell_enabled"])

    def test_hold_enabled_false(self):
        self.assertFalse(self._result["hold_enabled"])

    def test_positions_created_zero(self):
        self.assertEqual(self._result["positions_created"], 0)

    def test_pnl_created_zero(self):
        self.assertEqual(self._result["pnl_created"], 0)

    def test_paper_decisions_created_zero(self):
        self.assertEqual(self._result["paper_decisions_created"], 0)

    def test_retrieval_activation_false(self):
        self.assertFalse(self._result["retrieval_activation"])

    def test_clean_only_true(self):
        self.assertTrue(self._result["clean_only"])


# ===========================================================================
# Proof 20 — Hard locks all True
# ===========================================================================

class LaneVHardLocksTests(_VDbBase):
    _EXPECTED_HARD_LOCKS = {
        "no_retrieval_activation",
        "no_paper_decisions",
        "no_buy_sell_hold",
        "no_positions",
        "no_pnl",
        "no_live_trading",
        "no_wallet_private_key",
        "no_paid_api",
        "no_source_fetching",
        "no_scheduler_runtime_expansion",
        "no_scoring_ranking_confidence",
        "no_embeddings_vectors",
    }

    def setUp(self):
        super().setUp()
        self._result = self._report()

    def test_hard_locks_key_present(self):
        self.assertIn("hard_locks", self._result)

    def test_all_hard_lock_keys_present(self):
        locks = self._result["hard_locks"]
        for key in self._EXPECTED_HARD_LOCKS:
            self.assertIn(key, locks)

    def test_all_hard_locks_are_true(self):
        locks = self._result["hard_locks"]
        for key in self._EXPECTED_HARD_LOCKS:
            self.assertTrue(locks[key], f"hard_lock[{key}] should be True")

    def test_no_retrieval_activation_is_true(self):
        self.assertTrue(self._result["hard_locks"]["no_retrieval_activation"])

    def test_no_paper_decisions_is_true(self):
        self.assertTrue(self._result["hard_locks"]["no_paper_decisions"])

    def test_no_scoring_ranking_confidence_is_true(self):
        self.assertTrue(self._result["hard_locks"]["no_scoring_ranking_confidence"])


# ===========================================================================
# Proof 21 — db_path=None → BLOCKED
# ===========================================================================

class LaneVBlockedNonePathTests(unittest.TestCase):
    def test_none_path_returns_blocked_status(self):
        r = build_clean_memory_retrieval_report(None)
        self.assertEqual(r["lane_v_status"], LANE_V_STATUS_BLOCKED)

    def test_none_path_has_blocked_reasons(self):
        r = build_clean_memory_retrieval_report(None)
        self.assertIsInstance(r["blocked_reasons"], list)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_none_path_clean_only_still_true(self):
        r = build_clean_memory_retrieval_report(None)
        self.assertTrue(r["clean_only"])

    def test_none_path_retrieval_activation_false(self):
        r = build_clean_memory_retrieval_report(None)
        self.assertFalse(r["retrieval_activation"])


# ===========================================================================
# Proof 22 — Missing file → BLOCKED
# ===========================================================================

class LaneVBlockedMissingFileTests(unittest.TestCase):
    def test_missing_file_returns_blocked_status(self):
        r = build_clean_memory_retrieval_report("/nonexistent/printer_v1.sqlite3")
        self.assertEqual(r["lane_v_status"], LANE_V_STATUS_BLOCKED)

    def test_missing_file_has_blocked_reasons(self):
        r = build_clean_memory_retrieval_report("/nonexistent/printer_v1.sqlite3")
        self.assertIsInstance(r["blocked_reasons"], list)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_missing_file_hard_locks_present(self):
        r = build_clean_memory_retrieval_report("/nonexistent/printer_v1.sqlite3")
        self.assertIn("hard_locks", r)


# ===========================================================================
# Proof 23 — Zero clean memories is valid
# ===========================================================================

class LaneVZeroCleanMemoriesTests(_VDbBase):
    def setUp(self):
        super().setUp()
        # Insert a token/pair but no episodes at all
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        self._result = self._report()

    def test_status_is_ready_not_blocked(self):
        self.assertEqual(self._result["lane_v_status"], LANE_V_STATUS_READY)

    def test_clean_memory_count_is_zero(self):
        self.assertEqual(self._result["clean_memory_count"], 0)

    def test_selected_clean_memory_ids_is_empty_list(self):
        self.assertEqual(self._result["selected_clean_memory_ids"], [])

    def test_selected_window_ids_is_empty_list(self):
        self.assertEqual(self._result["selected_window_ids"], [])

    def test_group_summary_is_empty(self):
        self.assertEqual(self._result["group_summary"], [])

    def test_insufficient_label_present(self):
        self.assertIn(LABEL_INSUFFICIENT_CLEAN_MEMORY, self._result["report_labels"])


# ===========================================================================
# Proof 24 — Excluded counts are reported correctly
# ===========================================================================

class LaneVExcludedCountsTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        # 2 clean
        for _ in range(2):
            wid = self._insert_window(tid, pid)
            self._insert_clean_episode(tid, pid, wid)
        # 1 dirty
        wid_d = self._insert_window(tid, pid)
        self._insert_dirty_episode(tid, pid, wid_d)
        # 1 do_not_train
        wid_dnt = self._insert_window(tid, pid)
        self._insert_do_not_train_episode(tid, pid, wid_dnt)
        # 1 support_only
        wid_5m = self._insert_window(tid, pid, window_kind="WINDOW_5M_MICRO_EVENT")
        self._insert_support_only_episode(tid, pid, wid_5m)
        self._result = self._report()

    def test_clean_count_is_2(self):
        self.assertEqual(self._result["clean_memory_count"], 2)

    def test_dirty_excluded_count_is_1(self):
        self.assertEqual(self._result["dirty_memory_excluded_count"], 1)

    def test_do_not_train_excluded_count_is_1(self):
        self.assertEqual(self._result["do_not_train_excluded_count"], 1)

    def test_support_only_excluded_count_is_1(self):
        self.assertEqual(self._result["support_only_excluded_count"], 1)


# ===========================================================================
# Proof 25 — SAME_WINDOW_KIND label
# ===========================================================================

class LaneVSameWindowKindLabelTests(_VDbBase):
    def setUp(self):
        super().setUp()
        tid = self._insert_token()
        pid = self._insert_pair(tid)
        for _ in range(2):
            wid = self._insert_window(tid, pid, window_kind="WINDOW_15M")
            self._insert_clean_episode(tid, pid, wid, window_kind="WINDOW_15M")
        self._result = self._report()

    def test_same_window_kind_label_present(self):
        self.assertIn(LABEL_SAME_WINDOW_KIND, self._result["report_labels"])

    def test_window_kind_filter_stored_in_filters_applied(self):
        r = build_clean_memory_retrieval_report(
            self.db_path, window_kind="WINDOW_15M"
        )
        self.assertEqual(r["filters_applied"]["window_kind"], "WINDOW_15M")


if __name__ == "__main__":
    unittest.main()
