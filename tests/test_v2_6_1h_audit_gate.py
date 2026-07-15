"""V2-6 1h audit gate repair — focused verification.

Proves the window-kind-specific E2Q repair:
- valid WINDOW_15M behavior is unchanged;
- WINDOW_5M_MICRO_EVENT remains invalid as a main memory (support-only);
- a genuine, complete WINDOW_1H can enter audit;
- fake, short, incomplete, mismatched, or ungoverned WINDOW_1H stays blocked;
- dirty/stale WINDOW_1H classifies DIRTY (do_not_train), never clean;
- WINDOW_4H/12H/24H are not implicitly enabled;
- retrieval and financial tables remain zero-delta.

Fixtures and temporary DBs only. No source calls, scheduler runtime, persistent
DB mutation, or 1h proof.
"""

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.e2q_memory_window_audit import (
    E2Q_1H_MIN_ELAPSED_SECONDS,
    E2Q_STATUS_BLOCKED,
    E2Q_STATUS_CLEAN_CANDIDATE,
    E2Q_STATUS_DIRTY,
    E2Q_VALID_MAIN_WINDOW_KINDS,
    audit_15m_memory_window,
)

_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_MINT2 = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
_PAIR = "V26PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_T0 = datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db)

    def tearDown(self):
        self._tmp.cleanup()

    def _c(self):
        conn = sqlite3.connect(str(self.db))
        conn.row_factory = sqlite3.Row
        return conn

    def _count(self, table):
        conn = self._c()
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _token(self, conn, mint=_MINT):
        return int(conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status,created_at,updated_at)"
            " VALUES (?,'solana','TRACKING',?,?)", (mint, _iso(_T0), _iso(_T0)),
        ).lastrowid)

    def _pair(self, conn, token_id, addr=_PAIR):
        return int(conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint,created_at,updated_at)"
            " VALUES (?,?,?,?,?)", (token_id, addr, addr, _iso(_T0), _iso(_T0)),
        ).lastrowid)

    def _snap(self, conn, token_id, pair_id, captured, source_status="COMPLETE", quality="CLEAN_DATA"):
        return int(conn.execute(
            "INSERT INTO printer_token_snapshots(token_id,pair_id,captured_at,tracking_lane,"
            "snapshot_mode,source_status,data_quality_label,created_at)"
            " VALUES (?,?,?,'TRACK_FAST','FIRST_15M_CYCLE',?,?,?)",
            (token_id, pair_id, _iso(captured), source_status, quality, _iso(_T0)),
        ).lastrowid)

    def _window(self, conn, *, token_id, pair_id, window_kind, end_snap_id,
                window_status="WINDOW_CLOSED", data_quality="CLEAN_DATA",
                window_start_at=None, window_end_at=None,
                snapshot_start_id=None, snapshot_end_id=None):
        ctx = {"snapshot_id": end_snap_id, "created_by": "lane_e2o_1h"}
        return int(conn.execute(
            """INSERT INTO printer_memory_windows(
                 token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                 data_quality_label,do_not_train,window_status,supporting_context_json,
                 created_by_phase,created_at,updated_at,window_start_at,window_end_at,
                 snapshot_start_id,snapshot_end_id)
               VALUES(?,?,?,?,?,'PARTIAL_MEMORY',?,0,?,?,'lane_e2o_1h',?,?,?,?,?,?)""",
            (token_id, pair_id, window_kind, _iso(_T0), _iso(_T0), data_quality,
             window_status, json.dumps(ctx, sort_keys=True), _iso(_T0), _iso(_T0),
             window_start_at, window_end_at, snapshot_start_id, snapshot_end_id),
        ).lastrowid)

    def _run(self, window_id):
        conn = self._c()
        try:
            r = audit_15m_memory_window(conn, window_id)
            conn.commit()
        finally:
            conn.close()
        return r

    def _read(self, window_id):
        conn = self._c()
        try:
            return conn.execute("SELECT * FROM printer_memory_windows WHERE id=?", (window_id,)).fetchone()
        finally:
            conn.close()

    def _genuine_1h(self, *, span_seconds=3000, end_quality="CLEAN_DATA",
                    end_source="COMPLETE", start_token_mint=None, window_quality="CLEAN_DATA"):
        """Insert a genuine WINDOW_1H window; return window_id."""
        conn = self._c()
        try:
            tok = self._token(conn)
            pair = self._pair(conn, tok)
            start_tok = tok
            if start_token_mint is not None:
                start_tok = self._token(conn, start_token_mint)
            start = self._snap(conn, start_tok, pair, _T0)
            end = self._snap(conn, tok, pair, _T0 + timedelta(seconds=span_seconds),
                             source_status=end_source, quality=end_quality)
            win = self._window(
                conn, token_id=tok, pair_id=pair, window_kind="WINDOW_1H",
                end_snap_id=end, data_quality=window_quality,
                window_start_at=_iso(_T0),
                window_end_at=_iso(_T0 + timedelta(seconds=span_seconds)),
                snapshot_start_id=start, snapshot_end_id=end,
            )
            conn.commit()
        finally:
            conn.close()
        return win

    def _clean_15m(self, *, quality="CLEAN_DATA"):
        conn = self._c()
        try:
            tok = self._token(conn)
            pair = self._pair(conn, tok)
            snap = self._snap(conn, tok, pair, _T0)
            win = self._window(conn, token_id=tok, pair_id=pair, window_kind="WINDOW_15M",
                               end_snap_id=snap, data_quality=quality)
            conn.commit()
        finally:
            conn.close()
        return win


class Valid15mUnchanged(_Base):
    def test_clean_15m_still_clean_candidate(self):
        self.assertEqual(self._run(self._clean_15m())["e2q_status"], E2Q_STATUS_CLEAN_CANDIDATE)

    def test_acceptable_partial_15m_audit_only(self):
        r = self._run(self._clean_15m(quality="ACCEPTABLE_PARTIAL_DATA"))
        self.assertEqual(r["e2q_status"], "E2Q_AUDIT_ONLY")

    def test_valid_main_kinds_are_15m_and_1h(self):
        # WINDOW_4H was intentionally added to E2Q_VALID_MAIN_WINDOW_KINDS in
        # V2-8.1 (commit 3776716), which introduced genuine 4h structural/
        # continuity auditing alongside 1h. This assertion predates that and
        # is updated to match the approved V2-8.1 contract, not weakened.
        self.assertEqual(
            E2Q_VALID_MAIN_WINDOW_KINDS,
            frozenset({"WINDOW_15M", "WINDOW_1H", "WINDOW_4H"}),
        )


class FiveMinuteInvalid(_Base):
    def test_5m_blocked_support_only(self):
        conn = self._c()
        try:
            tok = self._token(conn); pair = self._pair(conn, tok)
            snap = self._snap(conn, tok, pair, _T0)
            win = self._window(conn, token_id=tok, pair_id=pair,
                               window_kind="WINDOW_5M_MICRO_EVENT", end_snap_id=snap)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win)
        self.assertEqual(r["e2q_status"], E2Q_STATUS_BLOCKED)
        self.assertIn("5m", " ".join(r["blocked_reasons"]).lower())
        self.assertIn("support-only", " ".join(r["blocked_reasons"]).lower())
        self.assertIsNone(self._read(win)["memory_quality_label"])


class GenuineOneHourAdmitted(_Base):
    def test_genuine_1h_clean_candidate(self):
        r = self._run(self._genuine_1h())
        self.assertEqual(r["e2q_status"], E2Q_STATUS_CLEAN_CANDIDATE)

    def test_genuine_1h_writes_quality_and_do_not_train_zero(self):
        win = self._genuine_1h()
        self._run(win)
        row = self._read(win)
        self.assertEqual(row["memory_quality_label"], "PARTIAL_MEMORY")
        self.assertEqual(row["do_not_train"], 0)

    def test_genuine_1h_at_exact_minimum_admitted(self):
        r = self._run(self._genuine_1h(span_seconds=int(E2Q_1H_MIN_ELAPSED_SECONDS)))
        self.assertEqual(r["e2q_status"], E2Q_STATUS_CLEAN_CANDIDATE)


class BadOneHourBlockedOrDirty(_Base):
    def test_short_1h_blocked(self):
        r = self._run(self._genuine_1h(span_seconds=900))
        self.assertEqual(r["e2q_status"], E2Q_STATUS_BLOCKED)
        self.assertIn("below the genuine 1h minimum", " ".join(r["blocked_reasons"]))

    def test_relabelled_1h_missing_timestamps_blocked(self):
        conn = self._c()
        try:
            tok = self._token(conn); pair = self._pair(conn, tok)
            snap = self._snap(conn, tok, pair, _T0)
            # WINDOW_1H with NULL window_start_at/end_at and NULL anchors.
            win = self._window(conn, token_id=tok, pair_id=pair, window_kind="WINDOW_1H",
                               end_snap_id=snap)
            conn.commit()
        finally:
            conn.close()
        r = self._run(win)
        self.assertEqual(r["e2q_status"], E2Q_STATUS_BLOCKED)
        self.assertIsNone(self._read(win)["memory_quality_label"])

    def test_ungoverned_1h_missing_anchors_blocked(self):
        conn = self._c()
        try:
            tok = self._token(conn); pair = self._pair(conn, tok)
            end = self._snap(conn, tok, pair, _T0 + timedelta(seconds=3000))
            # Real timestamps but NO snapshot anchors → ungoverned.
            win = self._window(conn, token_id=tok, pair_id=pair, window_kind="WINDOW_1H",
                               end_snap_id=end, window_start_at=_iso(_T0),
                               window_end_at=_iso(_T0 + timedelta(seconds=3000)))
            conn.commit()
        finally:
            conn.close()
        r = self._run(win)
        self.assertEqual(r["e2q_status"], E2Q_STATUS_BLOCKED)
        self.assertIn("governed snapshot anchors", " ".join(r["blocked_reasons"]))

    def test_mismatched_start_anchor_token_blocked(self):
        r = self._run(self._genuine_1h(start_token_mint=_MINT2))
        self.assertEqual(r["e2q_status"], E2Q_STATUS_BLOCKED)
        self.assertIn("snapshot_start", " ".join(r["blocked_reasons"]))

    def test_dirty_1h_classifies_dirty_not_clean(self):
        win = self._genuine_1h(end_quality="DIRTY_DATA")
        r = self._run(win)
        self.assertEqual(r["e2q_status"], E2Q_STATUS_DIRTY)
        row = self._read(win)
        self.assertEqual(row["memory_quality_label"], "DIRTY_MEMORY")
        self.assertEqual(row["do_not_train"], 1)

    def test_stale_1h_classifies_dirty(self):
        r = self._run(self._genuine_1h(end_source="STALE", end_quality="STALE_DATA"))
        self.assertEqual(r["e2q_status"], E2Q_STATUS_DIRTY)

    def test_open_1h_blocked(self):
        conn = self._c()
        try:
            tok = self._token(conn); pair = self._pair(conn, tok)
            start = self._snap(conn, tok, pair, _T0)
            end = self._snap(conn, tok, pair, _T0 + timedelta(seconds=3000))
            win = self._window(conn, token_id=tok, pair_id=pair, window_kind="WINDOW_1H",
                               end_snap_id=end, window_status="WINDOW_OPEN",
                               window_start_at=_iso(_T0),
                               window_end_at=_iso(_T0 + timedelta(seconds=3000)),
                               snapshot_start_id=start, snapshot_end_id=end)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self._run(win)["e2q_status"], E2Q_STATUS_BLOCKED)


class LongerKindsNotEnabled(_Base):
    def _kind_blocked(self, kind):
        conn = self._c()
        try:
            tok = self._token(conn); pair = self._pair(conn, tok)
            snap = self._snap(conn, tok, pair, _T0)
            win = self._window(conn, token_id=tok, pair_id=pair, window_kind=kind, end_snap_id=snap)
            conn.commit()
        finally:
            conn.close()
        return self._run(win)

    def test_4h_not_enabled(self):
        # V2-8.1 (commit 3776716) intentionally enabled WINDOW_4H as a valid
        # main window kind with its own genuine-continuation structural
        # check (_validate_genuine_4h_window), rather than rejecting it
        # outright. A minimal fixture window with no anchored boundaries or
        # governed snapshot anchors is therefore still BLOCKED, but for that
        # specific structural reason instead of a blanket "not enabled".
        r = self._kind_blocked("WINDOW_4H")
        self.assertEqual(r["e2q_status"], E2Q_STATUS_BLOCKED)
        self.assertIn(
            "missing anchored boundaries or governed snapshot anchors",
            " ".join(r["blocked_reasons"]),
        )

    def test_12h_not_enabled(self):
        self.assertEqual(self._kind_blocked("WINDOW_12H")["e2q_status"], E2Q_STATUS_BLOCKED)

    def test_24h_not_enabled(self):
        self.assertEqual(self._kind_blocked("WINDOW_24H")["e2q_status"], E2Q_STATUS_BLOCKED)


class ZeroDeltaLocks(_Base):
    def test_no_retrieval_or_financial_writes_for_1h(self):
        before = {t: self._count(t) for t in (
            "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
            "printer_paper_decisions", "printer_paper_positions",
            "printer_paper_trade_events", "printer_paper_trade_audits",
            "printer_paper_audit_reports", "printer_memories", "printer_episodes")}
        self._run(self._genuine_1h())
        after = {t: self._count(t) for t in before}
        self.assertEqual(before, after)

    def test_genuine_1h_creates_no_extra_windows(self):
        win = self._genuine_1h()
        n_before = self._count("printer_memory_windows")
        self._run(win)
        self.assertEqual(self._count("printer_memory_windows"), n_before)


if __name__ == "__main__":
    unittest.main()
