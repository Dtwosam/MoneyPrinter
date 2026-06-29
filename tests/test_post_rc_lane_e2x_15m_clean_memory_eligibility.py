from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.operator_cli.e2x_15m_clean_memory_eligibility import (
    E2X_LANE_NAME,
    build_e2x_15m_clean_memory_eligibility_report,
)


class _DbBase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "printer_v1.sqlite3"
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                """
                CREATE TABLE printer_memory_windows (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    token_id INTEGER,
                    pair_id INTEGER,
                    window_kind TEXT,
                    window_status TEXT,
                    memory_status TEXT,
                    memory_quality_label TEXT,
                    data_quality_label TEXT,
                    do_not_train INTEGER DEFAULT 0,
                    opened_at TEXT,
                    closed_at TEXT,
                    rejection_reasons_json TEXT,
                    supporting_context_json TEXT,
                    created_by_phase TEXT,
                    created_at TEXT,
                    updated_at TEXT
                )
                """
            )
            conn.commit()
        finally:
            conn.close()

    def tearDown(self):
        self.tmp.cleanup()

    def _connect(self):
        return sqlite3.connect(self.db_path)

    def _insert_window(
        self,
        conn,
        *,
        token_id=1,
        pair_id=1,
        window_kind="WINDOW_15M",
        window_status="WINDOW_CLOSED",
        memory_status="PARTIAL_MEMORY",
        memory_quality_label="PARTIAL_MEMORY",
        data_quality_label="CLEAN_DATA",
        do_not_train=0,
        ctx=None,
        rejection_reasons=None,
    ):
        if ctx is None:
            ctx = {
                "snapshot_id": 123,
                "e2q_audited": True,
                "e2q_audited_by": "lane_e2q",
            }
        if rejection_reasons is None:
            rejection_reasons = []
        cur = conn.execute(
            """
            INSERT INTO printer_memory_windows (
                token_id, pair_id, window_kind, window_status,
                memory_status, memory_quality_label, data_quality_label,
                do_not_train, opened_at, closed_at, rejection_reasons_json,
                supporting_context_json, created_by_phase, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token_id,
                pair_id,
                window_kind,
                window_status,
                memory_status,
                memory_quality_label,
                data_quality_label,
                do_not_train,
                "2026-06-29T10:00:00+00:00",
                "2026-06-29T10:15:00+00:00",
                json.dumps(rejection_reasons),
                json.dumps(ctx),
                "test",
                "2026-06-29T10:15:00+00:00",
                "2026-06-29T10:15:00+00:00",
            ),
        )
        return cur.lastrowid

    def _run(self, operator_approved=True):
        return build_e2x_15m_clean_memory_eligibility_report(
            self.db_path,
            operator_approved=operator_approved,
        )


class LaneE2XApprovalTests(_DbBase):
    def test_operator_approval_required(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["e2x_status"], "E2X_REVIEW_BLOCKED")
        self.assertIn("OPERATOR_APPROVAL_REQUIRED", r["blocked_reasons"])
        self.assertFalse(r["operator_approved"])


class LaneE2XEmptyReportTests(_DbBase):
    def test_empty_report_ready(self):
        r = self._run()
        self.assertEqual(r["lane"], E2X_LANE_NAME)
        self.assertEqual(r["e2x_status"], "E2X_REVIEW_READY")
        self.assertEqual(r["total_15m_window_count"], 0)

    def test_no_creation_gate_on_empty_report(self):
        r = self._run()
        self.assertFalse(r["clean_memory_creation_ready"])
        self.assertEqual(r["clean_memory_rows_created"], 0)
        self.assertFalse(r["retrieval_activated"])
        self.assertEqual(r["paper_decisions_created"], 0)
        self.assertFalse(r["buy_enabled"])

    def test_read_only_delta_empty(self):
        r = self._run()
        self.assertEqual(r["read_only_delta_violations"], [])


class LaneE2XEligibilityTests(_DbBase):
    def test_partial_clean_closed_e2q_window_is_review_candidate(self):
        conn = self._connect()
        try:
            window_id = self._insert_window(conn)
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["review_candidate_count"], 1)
        self.assertEqual(r["review_candidate_ids"], [window_id])
        self.assertEqual(
            r["classification_counts"]["eligible_for_future_clean_memory_review"],
            1,
        )
        self.assertFalse(r["clean_memory_creation_ready"])

    def test_candidate_review_does_not_create_clean_memory(self):
        conn = self._connect()
        try:
            self._insert_window(conn)
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        item = r["latest_15m_reviews"][0]
        self.assertTrue(item["review_only"])
        self.assertFalse(item["creates_clean_memory"])
        self.assertFalse(item["activates_retrieval"])
        self.assertFalse(item["activates_paper_decision"])
        self.assertFalse(item["unlocks_buy"])


class LaneE2XBlockedTests(_DbBase):
    def test_dirty_do_not_train_blocked(self):
        conn = self._connect()
        try:
            self._insert_window(
                conn,
                do_not_train=1,
                memory_quality_label="AUDIT_ONLY_MEMORY",
                memory_status="AUDIT_ONLY",
                data_quality_label="MISSING_CRITICAL_DATA",
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["review_candidate_count"], 0)
        self.assertEqual(r["classification_counts"]["blocked_dirty_or_do_not_train"], 1)

    def test_legacy_clean_memory_label_blocked(self):
        conn = self._connect()
        try:
            window_id = self._insert_window(
                conn,
                memory_status="CLEAN_MEMORY",
                memory_quality_label="CLEAN_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["review_candidate_count"], 0)
        self.assertEqual(r["legacy_clean_memory_label_count"], 1)
        self.assertEqual(r["legacy_clean_memory_label_ids"], [window_id])
        self.assertEqual(
            r["classification_counts"]["blocked_legacy_clean_memory_label"],
            1,
        )

    def test_missing_snapshot_link_blocked(self):
        conn = self._connect()
        try:
            self._insert_window(conn, ctx={"e2q_audited": True})
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["review_candidate_count"], 0)
        self.assertEqual(r["classification_counts"]["blocked_missing_snapshot_link"], 1)

    def test_missing_e2q_audit_blocked(self):
        conn = self._connect()
        try:
            self._insert_window(conn, ctx={"snapshot_id": 123})
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["review_candidate_count"], 0)
        self.assertEqual(r["classification_counts"]["blocked_not_e2q_audited"], 1)

    def test_not_closed_blocked(self):
        conn = self._connect()
        try:
            self._insert_window(conn, window_status="WINDOW_AUDIT_ONLY")
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["classification_counts"]["blocked_not_closed"], 1)

    def test_5m_window_ignored(self):
        conn = self._connect()
        try:
            self._insert_window(conn, window_kind="WINDOW_5M_MICRO_EVENT")
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["total_15m_window_count"], 0)
        self.assertEqual(r["review_candidate_count"], 0)


class LaneE2XCountAndLockTests(_DbBase):
    def test_multiple_candidates_counted(self):
        conn = self._connect()
        try:
            first = self._insert_window(conn, token_id=1, pair_id=1)
            second = self._insert_window(conn, token_id=2, pair_id=2)
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertEqual(r["review_candidate_count"], 2)
        self.assertEqual(r["review_candidate_ids"], [second, first])

    def test_hard_locks_all_true(self):
        r = self._run()
        self.assertTrue(all(r["hard_locks"].values()))

    def test_locked_state_all_false(self):
        r = self._run()
        self.assertFalse(any(r["locked_state"].values()))

    def test_next_lane_is_operator_review(self):
        r = self._run()
        self.assertEqual(
            r["next_recommended_lane"],
            "operator review required before any clean-memory creation boundary",
        )

    def test_table_absent_clean_memory_is_reported_without_creation(self):
        r = self._run()
        self.assertEqual(r["table_counts_before"]["printer_memories"], "table_absent")
        self.assertEqual(r["table_counts_after"]["printer_memories"], "table_absent")
        self.assertEqual(r["read_only_delta_violations"], [])


if __name__ == "__main__":
    unittest.main()
