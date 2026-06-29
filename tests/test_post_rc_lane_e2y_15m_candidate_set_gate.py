from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from printer_v1.operator_cli.e2y_15m_candidate_set_gate import (
    E2Y_LANE_NAME,
    build_e2y_15m_candidate_set_gate_report,
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

    def _insert_candidate(
        self,
        conn,
        *,
        token_id=13,
        pair_id=13,
        snapshot_id=91,
        window_kind="WINDOW_15M",
        window_status="WINDOW_CLOSED",
        data_quality_label="CLEAN_DATA",
        memory_status="PARTIAL_MEMORY",
        memory_quality_label="PARTIAL_MEMORY",
        do_not_train=0,
        e2q_audited=True,
    ):
        ctx = {
            "snapshot_id": snapshot_id,
            "e2q_audited": e2q_audited,
            "e2q_audited_by": "lane_e2q" if e2q_audited else None,
            "snapshot_mode": "FIRST_15M_CYCLE",
            "tracking_lane": "TRACK_FAST",
        }
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
                "[]",
                json.dumps(ctx),
                "test",
                "2026-06-29T10:15:00+00:00",
                "2026-06-29T10:15:00+00:00",
            ),
        )
        return cur.lastrowid

    def _insert_full_candidate_set(self, **overrides):
        conn = self._connect()
        try:
            ids = []
            for snapshot_id in [91, 92, 93, 94, 95]:
                kwargs = dict(overrides)
                kwargs.setdefault("snapshot_id", snapshot_id)
                ids.append(self._insert_candidate(conn, **kwargs))
            conn.commit()
            return ids
        finally:
            conn.close()

    def _run(self, operator_approved=True):
        return build_e2y_15m_candidate_set_gate_report(
            self.db_path,
            operator_approved=operator_approved,
        )


class LaneE2YApprovalTests(_DbBase):
    def test_operator_approval_required(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["e2y_status"], "E2Y_SET_GATE_BLOCKED")
        self.assertIn("OPERATOR_APPROVAL_REQUIRED", r["blocked_reasons"])
        self.assertFalse(r["set_gate_passed"])


class LaneE2YPassingSetTests(_DbBase):
    def test_full_candidate_set_passes(self):
        ids = self._insert_full_candidate_set()
        r = self._run()
        self.assertEqual(r["lane"], E2Y_LANE_NAME)
        self.assertEqual(r["e2y_status"], "E2Y_SET_GATE_READY")
        self.assertTrue(r["set_gate_passed"])
        self.assertEqual(r["candidate_set_summary"]["candidate_ids"], list(reversed(ids)))
        self.assertEqual(r["candidate_set_summary"]["snapshot_ids"], [91, 92, 93, 94, 95])

    def test_full_candidate_set_is_review_only(self):
        self._insert_full_candidate_set()
        r = self._run()
        self.assertFalse(r["clean_memory_creation_ready"])
        self.assertEqual(r["clean_memory_rows_created"], 0)
        self.assertFalse(r["retrieval_activated"])
        self.assertEqual(r["paper_decisions_created"], 0)
        self.assertFalse(r["buy_enabled"])

    def test_hard_locks_all_true(self):
        self._insert_full_candidate_set()
        r = self._run()
        self.assertTrue(all(r["hard_locks"].values()))

    def test_locked_state_all_false(self):
        self._insert_full_candidate_set()
        r = self._run()
        self.assertFalse(any(r["locked_state"].values()))


class LaneE2YBlockedSetTests(_DbBase):
    def test_less_than_five_candidates_blocks_set_gate(self):
        conn = self._connect()
        try:
            for snapshot_id in [91, 92, 93, 94]:
                self._insert_candidate(conn, snapshot_id=snapshot_id)
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertFalse(r["set_gate_passed"])
        self.assertFalse(r["set_gate"]["candidate_count_is_5"])

    def test_mixed_token_pair_blocks_set_gate(self):
        conn = self._connect()
        try:
            for snapshot_id in [91, 92, 93, 94]:
                self._insert_candidate(conn, snapshot_id=snapshot_id)
            self._insert_candidate(conn, token_id=14, pair_id=14, snapshot_id=95)
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertFalse(r["set_gate_passed"])
        self.assertFalse(r["set_gate"]["all_same_token_pair"])

    def test_clean_memory_label_blocks_set_gate(self):
        conn = self._connect()
        try:
            for snapshot_id in [91, 92, 93, 94]:
                self._insert_candidate(conn, snapshot_id=snapshot_id)
            self._insert_candidate(
                conn,
                snapshot_id=95,
                memory_status="CLEAN_MEMORY",
                memory_quality_label="CLEAN_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertFalse(r["set_gate_passed"])
        self.assertFalse(r["set_gate"]["candidate_count_is_5"])
        self.assertTrue(r["set_gate"]["no_clean_memory_labels_in_candidate_set"])

    def test_dirty_do_not_train_candidate_excluded_and_blocks_count(self):
        conn = self._connect()
        try:
            for snapshot_id in [91, 92, 93, 94]:
                self._insert_candidate(conn, snapshot_id=snapshot_id)
            self._insert_candidate(
                conn,
                snapshot_id=95,
                do_not_train=1,
                data_quality_label="MISSING_CRITICAL_DATA",
                memory_status="AUDIT_ONLY",
                memory_quality_label="AUDIT_ONLY_MEMORY",
            )
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertFalse(r["set_gate_passed"])
        self.assertFalse(r["set_gate"]["candidate_count_is_5"])

    def test_missing_e2q_candidate_excluded_and_blocks_count(self):
        conn = self._connect()
        try:
            for snapshot_id in [91, 92, 93, 94]:
                self._insert_candidate(conn, snapshot_id=snapshot_id)
            self._insert_candidate(conn, snapshot_id=95, e2q_audited=False)
            conn.commit()
        finally:
            conn.close()

        r = self._run()
        self.assertFalse(r["set_gate_passed"])
        self.assertFalse(r["set_gate"]["candidate_count_is_5"])

    def test_duplicate_snapshot_ids_block_set_gate(self):
        self._insert_full_candidate_set(snapshot_id=91)
        r = self._run()
        self.assertFalse(r["set_gate_passed"])
        self.assertFalse(r["set_gate"]["snapshot_ids_are_strictly_increasing"])


class LaneE2YNoCreationTests(_DbBase):
    def test_read_only_delta_clean(self):
        self._insert_full_candidate_set()
        r = self._run()
        self.assertEqual(r["read_only_delta_violations"], [])
        self.assertTrue(r["set_gate"]["read_only_delta_clean"])

    def test_table_absent_printer_memories_remains_absent(self):
        self._insert_full_candidate_set()
        r = self._run()
        self.assertEqual(r["table_counts_before"]["printer_memories"], "table_absent")
        self.assertEqual(r["table_counts_after"]["printer_memories"], "table_absent")

    def test_next_lane_is_operator_review(self):
        self._insert_full_candidate_set()
        r = self._run()
        self.assertEqual(
            r["next_recommended_lane"],
            "operator review required before any clean-memory creation boundary",
        )


if __name__ == "__main__":
    unittest.main()
