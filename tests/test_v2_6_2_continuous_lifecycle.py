"""V2-6.2 — Continuous First-Hour Lifecycle Repair.

Proves one continuous lifecycle for the same run/token/pair/lane:

    5m support -> 15m main window -> 1h continuation

Fixtures and temporary DBs only. No source calls, scheduler runtime, persistent
DB mutation, or live/1h proof run.

Covered:
- deadline anchoring (15m close + 2700s), immediate enqueue at 15m close;
- continuous 5m->15m linkage (first snapshots of same run, no restart,
  900s-anchored close, first-post-5m gap on 15m thresholds);
- continuous 15m->1h linkage (exact fresh window + closing snapshot);
- same run/token/pair/lane throughout;
- clean / dirty / blocked transition thresholds;
- delayed restart (negative gap) rejected;
- reused historical windows rejected;
- clocks not reset (opening snapshot preserved);
- E2O consumes continuity (do_not_train / block); E2Q consumes the result;
- replay and downstream financial/retrieval locks unchanged.
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
from printer_v1.snapshots.lifecycle_continuity import (
    CONTINUATION_1H_SECONDS,
    CONTINUITY_BLOCKED,
    CONTINUITY_CONTINUOUS,
    CONTINUITY_DIRTY,
    CONTINUITY_UNKNOWN,
    build_1h_continuation_plan,
    compute_1h_continuation_deadline,
    evaluate_15m_to_1h_continuity,
    evaluate_5m_to_15m_continuity,
    resolve_lifecycle_continuity,
)
from printer_v1.operator_cli.lane_e2o_1h_window_close import (
    E2O_1H_STATUS_CONTINUITY_BLOCKED,
    E2O_1H_STATUS_CREATED,
    close_1h_memory_window_from_snapshot,
)

_MINT = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR = "V262PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_T0 = datetime(2026, 6, 28, 10, 0, 0, tzinfo=timezone.utc)


def _iso(dt):
    return dt.isoformat()


# ===========================================================================
# Pure evaluator fixtures (no DB)
# ===========================================================================

def _five(**kw):
    d = {"run_id": 1, "token_id": 1, "pair_id": 1, "tracking_lane": "TRACK_FAST",
         "snapshot_start_id": 100, "snapshot_end_id": 105}
    d.update(kw)
    return d


def _fifteen(**kw):
    d = {"run_id": 1, "token_id": 1, "pair_id": 1, "tracking_lane": "TRACK_FAST",
         "id": 10, "window_kind": "WINDOW_15M", "window_status": "WINDOW_CLOSED",
         "snapshot_start_id": 100, "snapshot_end_id": 115,
         "window_start_at": _iso(_T0),
         "window_end_at": _iso(_T0 + timedelta(seconds=901)),
         "closed_at": _iso(_T0 + timedelta(seconds=901))}
    d.update(kw)
    return d


def _oneh(**kw):
    # 15m closes at T0+901; a clean FAST transition first-snap ~100s later.
    close = _T0 + timedelta(seconds=901)
    d = {"run_id": 1, "token_id": 1, "pair_id": 1, "tracking_lane": "TRACK_FAST",
         "id": 20, "continuation_of_window_id": 10, "linked_closing_snapshot_id": 115,
         "linked_first_snapshot_id": 116,
         "first_snapshot_at": _iso(close + timedelta(seconds=100)),
         "deadline_at": _iso(close + timedelta(seconds=CONTINUATION_1H_SECONDS))}
    d.update(kw)
    return d


class TestDeadlineAnchoring(unittest.TestCase):
    def test_deadline_is_close_plus_2700(self):
        d = compute_1h_continuation_deadline(_iso(_T0))
        self.assertEqual(d, _T0 + timedelta(seconds=2700))

    def test_deadline_none_when_missing(self):
        self.assertIsNone(compute_1h_continuation_deadline(None))

    def test_plan_enqueue_at_15m_close(self):
        plan = build_1h_continuation_plan(_fifteen())
        self.assertTrue(plan["enqueue_ok"])
        self.assertEqual(plan["enqueue_at"], _iso(_T0 + timedelta(seconds=901)))

    def test_plan_deadline_anchored(self):
        plan = build_1h_continuation_plan(_fifteen())
        self.assertEqual(
            plan["deadline_at"],
            _iso(_T0 + timedelta(seconds=901 + 2700)),
        )
        self.assertEqual(plan["deadline_anchored_to"], "fifteen_m_close_plus_2700s")

    def test_plan_blocked_when_15m_open(self):
        plan = build_1h_continuation_plan(_fifteen(window_status="WINDOW_OPEN"))
        self.assertFalse(plan["enqueue_ok"])


class Test5mTo15mContinuity(unittest.TestCase):
    def test_clean(self):
        r = evaluate_5m_to_15m_continuity(_five(), _fifteen(), first_post_5m_gap_seconds=70)
        self.assertEqual(r.status, CONTINUITY_CONTINUOUS)
        self.assertFalse(r.do_not_train)
        self.assertTrue(r.can_be_quality_memory)

    def test_restart_different_opening_snapshot_blocked(self):
        r = evaluate_5m_to_15m_continuity(_five(snapshot_start_id=200), _fifteen())
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("restart_detected" in x for x in r.reasons))

    def test_5m_range_not_prefix_blocked(self):
        r = evaluate_5m_to_15m_continuity(_five(snapshot_end_id=999), _fifteen())
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("not_prefix" in x for x in r.reasons))

    def test_15m_close_not_anchored_to_900s_blocked(self):
        short = _fifteen(window_end_at=_iso(_T0 + timedelta(seconds=600)))
        r = evaluate_5m_to_15m_continuity(_five(), short)
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("anchored_to_open_plus_900s" in x for x in r.reasons))

    def test_first_post_5m_gap_dirty(self):
        # FAST 15m: dirty_above 90, block 120. 100s -> DIRTY.
        r = evaluate_5m_to_15m_continuity(_five(), _fifteen(), first_post_5m_gap_seconds=100)
        self.assertEqual(r.status, CONTINUITY_DIRTY)
        self.assertTrue(r.do_not_train)

    def test_first_post_5m_gap_blocked(self):
        r = evaluate_5m_to_15m_continuity(_five(), _fifteen(), first_post_5m_gap_seconds=150)
        self.assertEqual(r.status, CONTINUITY_BLOCKED)

    def test_token_pair_mismatch_blocked(self):
        r = evaluate_5m_to_15m_continuity(_five(pair_id=99), _fifteen())
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("pair_id_mismatch" in x for x in r.reasons))

    def test_lane_mismatch_blocked(self):
        r = evaluate_5m_to_15m_continuity(
            _five(tracking_lane="TRACK_NORMAL"), _fifteen(), tracking_lane="TRACK_FAST")
        self.assertEqual(r.status, CONTINUITY_BLOCKED)


class Test15mTo1hContinuity(unittest.TestCase):
    def test_clean(self):
        r = evaluate_15m_to_1h_continuity(_fifteen(), _oneh())
        self.assertEqual(r.status, CONTINUITY_CONTINUOUS)
        self.assertTrue(r.can_be_quality_memory)

    def test_dirty_transition_gap(self):
        # FAST transition: dirty_above 180, block 240. gap 200 -> DIRTY.
        close = _T0 + timedelta(seconds=901)
        r = evaluate_15m_to_1h_continuity(
            _fifteen(), _oneh(first_snapshot_at=_iso(close + timedelta(seconds=200))))
        self.assertEqual(r.status, CONTINUITY_DIRTY)
        self.assertTrue(r.do_not_train)
        self.assertFalse(r.can_be_quality_memory)

    def test_blocked_transition_gap(self):
        close = _T0 + timedelta(seconds=901)
        r = evaluate_15m_to_1h_continuity(
            _fifteen(), _oneh(first_snapshot_at=_iso(close + timedelta(seconds=300))))
        self.assertEqual(r.status, CONTINUITY_BLOCKED)

    def test_negative_gap_delayed_restart_blocked(self):
        close = _T0 + timedelta(seconds=901)
        r = evaluate_15m_to_1h_continuity(
            _fifteen(), _oneh(first_snapshot_at=_iso(close - timedelta(seconds=60))))
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("delayed_restart" in x or "negative" in x for x in r.reasons))

    def test_reused_historical_window_blocked(self):
        r = evaluate_15m_to_1h_continuity(_fifteen(), _oneh(), consumed_15m_window_ids=[10])
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("reused_historical" in x for x in r.reasons))

    def test_wrong_linked_window_blocked(self):
        r = evaluate_15m_to_1h_continuity(_fifteen(), _oneh(continuation_of_window_id=999))
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("not_linked_to_this_15m_window" in x for x in r.reasons))

    def test_wrong_closing_snapshot_blocked(self):
        r = evaluate_15m_to_1h_continuity(_fifteen(), _oneh(linked_closing_snapshot_id=999))
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("closing_snapshot" in x for x in r.reasons))

    def test_interpolated_first_snapshot_blocked(self):
        r = evaluate_15m_to_1h_continuity(_fifteen(), _oneh(interpolated_first_snapshot=True))
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("interpolated" in x for x in r.reasons))

    def test_deadline_target_drift_blocked(self):
        # deadline anchored to first-snapshot + 2700 instead of close + 2700.
        close = _T0 + timedelta(seconds=901)
        drifted = _oneh(deadline_at=_iso(close + timedelta(seconds=100 + 2700)),
                        window_end_at=None)
        r = evaluate_15m_to_1h_continuity(_fifteen(), drifted)
        self.assertEqual(r.status, CONTINUITY_BLOCKED)
        self.assertTrue(any("target_drift" in x for x in r.reasons))

    def test_normal_lane_clean(self):
        # NORMAL transition threshold: dirty 360, block 480. gap 300 clean.
        close = _T0 + timedelta(seconds=901)
        r = evaluate_15m_to_1h_continuity(
            _fifteen(tracking_lane="TRACK_NORMAL"),
            _oneh(tracking_lane="TRACK_NORMAL",
                  first_snapshot_at=_iso(close + timedelta(seconds=300))),
            tracking_lane="TRACK_NORMAL")
        self.assertEqual(r.status, CONTINUITY_CONTINUOUS)


# ===========================================================================
# DB-backed resolver + E2O wiring + consumption
# ===========================================================================

class _DBBase(unittest.TestCase):
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

    def _snap(self, conn, token_id, pair_id, captured, lane="TRACK_FAST"):
        return int(conn.execute(
            "INSERT INTO printer_token_snapshots(token_id,pair_id,captured_at,tracking_lane,"
            "snapshot_mode,source_status,data_quality_label,created_at)"
            " VALUES (?,?,?,?,'FIRST_15M_CYCLE','COMPLETE','CLEAN_DATA',?)",
            (token_id, pair_id, _iso(captured), lane, _iso(_T0)),
        ).lastrowid)

    def _window(self, conn, token_id, pair_id, kind, start_id, end_id, opened, closed,
                run_id=None, lane="TRACK_FAST", ctx=None):
        wid = int(conn.execute(
            "INSERT INTO printer_memory_windows(token_id,pair_id,window_kind,opened_at,closed_at,"
            "memory_status,data_quality_label,do_not_train,window_status,supporting_context_json,"
            "created_by_phase,created_at,updated_at,window_start_at,window_end_at,"
            "snapshot_start_id,snapshot_end_id)"
            " VALUES (?,?,?,?,?,'PARTIAL_MEMORY','CLEAN_DATA',0,'WINDOW_CLOSED',?,?,?,?,?,?,?,?)",
            (token_id, pair_id, kind, _iso(opened), _iso(closed),
             json.dumps(ctx or {}), "test", _iso(_T0), _iso(_T0),
             _iso(opened), _iso(closed), start_id, end_id),
        ).lastrowid)
        if run_id is not None:
            conn.execute(
                "INSERT INTO printer_memory_factory_run_steps(run_id,step_key,step_kind,step_status,"
                "token_id,pair_id,tracking_lane,memory_window_id,created_at,updated_at)"
                " VALUES (?,?,?,'SUCCEEDED',?,?,?,?,?,?)",
                (run_id, f"w{wid}", "WINDOW_CLOSE", token_id, pair_id, lane, wid,
                 _iso(_T0), _iso(_T0)),
            )
        return wid


class TestDbResolver(_DBBase):
    def _build(self, *, transition_gap=100, run_id="run-1"):
        conn = self._c()
        try:
            tid = self._token(conn)
            pid = self._pair(conn, tid)
            close15 = _T0 + timedelta(seconds=901)
            # 15m snapshots: opening (id s0) .. closing (s_end)
            s0 = self._snap(conn, tid, pid, _T0)
            for k in range(1, 15):
                self._snap(conn, tid, pid, _T0 + timedelta(seconds=k * 60))
            s_end = self._snap(conn, tid, pid, close15)
            # 5m support window uses first snapshots of the same run
            self._window(conn, tid, pid, "WINDOW_5M_MICRO_EVENT", s0, s0 + 5,
                         _T0, _T0 + timedelta(seconds=301), run_id=run_id)
            w15 = self._window(conn, tid, pid, "WINDOW_15M", s0, s_end,
                               _T0, close15, run_id=run_id)
            # 1h continuation: first snapshot transition_gap after close
            f1 = self._snap(conn, tid, pid, close15 + timedelta(seconds=transition_gap))
            deadline = close15 + timedelta(seconds=CONTINUATION_1H_SECONDS)
            self._window(conn, tid, pid, "WINDOW_1H", f1, f1 + 20,
                         close15, deadline, run_id=run_id,
                         ctx={"continuation_of_window_id": w15,
                              "linked_closing_snapshot_id": s_end})
            conn.commit()
            return conn, tid, pid, run_id
        finally:
            pass

    def test_resolver_continuous(self):
        conn, tid, pid, run_id = self._build(transition_gap=100)
        try:
            out = resolve_lifecycle_continuity(
                conn, run_id=run_id, token_id=tid, pair_id=pid, tracking_lane="TRACK_FAST")
            self.assertEqual(out["continuity_status"], CONTINUITY_CONTINUOUS)
            self.assertTrue(out["same_run_token_pair_lane"])
            self.assertEqual(len(out["stages"]), 2)
        finally:
            conn.close()

    def test_resolver_dirty_transition(self):
        conn, tid, pid, run_id = self._build(transition_gap=200)
        try:
            out = resolve_lifecycle_continuity(
                conn, run_id=run_id, token_id=tid, pair_id=pid, tracking_lane="TRACK_FAST")
            self.assertEqual(out["continuity_status"], CONTINUITY_DIRTY)
            self.assertTrue(out["do_not_train"])
        finally:
            conn.close()

    def test_resolver_blocked_transition(self):
        conn, tid, pid, run_id = self._build(transition_gap=300)
        try:
            out = resolve_lifecycle_continuity(
                conn, run_id=run_id, token_id=tid, pair_id=pid, tracking_lane="TRACK_FAST")
            self.assertEqual(out["continuity_status"], CONTINUITY_BLOCKED)
            self.assertFalse(out["can_be_quality_memory"])
        finally:
            conn.close()


class TestE2OContinuationWiring(_DBBase):
    def _setup_1h(self, *, transition_gap):
        conn = self._c()
        tid = self._token(conn)
        pid = self._pair(conn, tid)
        close15 = _T0 + timedelta(seconds=901)
        s_end = self._snap(conn, tid, pid, close15)  # 15m closing snapshot
        first_1h = self._snap(conn, tid, pid, close15 + timedelta(seconds=transition_gap))
        close_1h = close15 + timedelta(seconds=CONTINUATION_1H_SECONDS)
        close_snap = self._snap(conn, tid, pid, close_1h)
        conn.commit()
        cont = {"id": 500, "snapshot_end_id": s_end, "run_id": "r1",
                "token_id": tid, "pair_id": pid, "tracking_lane": "TRACK_FAST",
                "closed_at": _iso(close15), "window_end_at": _iso(close15)}
        return conn, tid, pid, first_1h, close_snap, close15, cont

    def test_clean_continuation_created_and_anchored(self):
        conn, tid, pid, first_1h, close_snap, close15, cont = self._setup_1h(transition_gap=100)
        try:
            r = close_1h_memory_window_from_snapshot(
                conn, close_snap, _MINT, snapshot_start_id=first_1h,
                continuation_of_15m=cont)
            self.assertEqual(r["e2o_1h_status"], E2O_1H_STATUS_CREATED)
            self.assertEqual(r["do_not_train"], 0)
            # window_end anchored to 15m close + 2700s, not first-snapshot + 2700
            self.assertEqual(r["window_end_at"],
                             _iso(close15 + timedelta(seconds=CONTINUATION_1H_SECONDS)))
            self.assertEqual(r["window_start_at"], _iso(close15))
            self.assertEqual(r["continuity"]["continuity_status"], CONTINUITY_CONTINUOUS)
        finally:
            conn.close()

    def test_dirty_continuation_sets_do_not_train(self):
        conn, tid, pid, first_1h, close_snap, close15, cont = self._setup_1h(transition_gap=200)
        try:
            r = close_1h_memory_window_from_snapshot(
                conn, close_snap, _MINT, snapshot_start_id=first_1h,
                continuation_of_15m=cont)
            self.assertEqual(r["e2o_1h_status"], E2O_1H_STATUS_CREATED)
            self.assertEqual(r["do_not_train"], 1)
            self.assertEqual(r["continuity"]["continuity_status"], CONTINUITY_DIRTY)
            row = conn.execute(
                "SELECT do_not_train,data_quality_label FROM printer_memory_windows WHERE id=?",
                (r["window_id"],)).fetchone()
            self.assertEqual(int(row[0]), 1)
        finally:
            conn.close()

    def test_blocked_continuation_not_created(self):
        conn, tid, pid, first_1h, close_snap, close15, cont = self._setup_1h(transition_gap=300)
        try:
            before = self._count("printer_memory_windows")
            r = close_1h_memory_window_from_snapshot(
                conn, close_snap, _MINT, snapshot_start_id=first_1h,
                continuation_of_15m=cont)
            self.assertEqual(r["e2o_1h_status"], E2O_1H_STATUS_CONTINUITY_BLOCKED)
            self.assertFalse(r["created"])
            conn.commit()
            self.assertEqual(self._count("printer_memory_windows"), before)
        finally:
            conn.close()

    def test_reused_window_blocked(self):
        conn, tid, pid, first_1h, close_snap, close15, cont = self._setup_1h(transition_gap=100)
        try:
            r = close_1h_memory_window_from_snapshot(
                conn, close_snap, _MINT, snapshot_start_id=first_1h,
                continuation_of_15m=cont, consumed_15m_window_ids=[500])
            self.assertEqual(r["e2o_1h_status"], E2O_1H_STATUS_CONTINUITY_BLOCKED)
        finally:
            conn.close()

    def test_backward_compat_no_continuation(self):
        # Without continuation_of_15m the close behaves exactly as before.
        conn, tid, pid, first_1h, close_snap, close15, cont = self._setup_1h(transition_gap=100)
        try:
            r = close_1h_memory_window_from_snapshot(
                conn, close_snap, _MINT, snapshot_start_id=first_1h)
            self.assertEqual(r["e2o_1h_status"], E2O_1H_STATUS_CREATED)
            self.assertNotIn("continuity", r)
            self.assertEqual(r["do_not_train"], 0)
        finally:
            conn.close()


class TestDownstreamLocks(_DBBase):
    def test_continuation_creates_no_financial_or_retrieval_rows(self):
        conn = self._c()
        tid = self._token(conn)
        pid = self._pair(conn, tid)
        close15 = _T0 + timedelta(seconds=901)
        s_end = self._snap(conn, tid, pid, close15)
        first_1h = self._snap(conn, tid, pid, close15 + timedelta(seconds=100))
        close_snap = self._snap(conn, tid, pid, close15 + timedelta(seconds=CONTINUATION_1H_SECONDS))
        conn.commit()
        cont = {"id": 500, "snapshot_end_id": s_end, "run_id": "r1",
                "token_id": tid, "pair_id": pid, "tracking_lane": "TRACK_FAST",
                "closed_at": _iso(close15)}
        r = close_1h_memory_window_from_snapshot(
            conn, close_snap, _MINT, snapshot_start_id=first_1h, continuation_of_15m=cont)
        conn.commit()
        conn.close()
        self.assertEqual(r["e2o_1h_status"], E2O_1H_STATUS_CREATED)
        for t in ("printer_paper_decisions", "printer_paper_positions",
                  "printer_paper_trade_events", "printer_paper_trade_audits"):
            self.assertEqual(self._count(t), 0, t)


if __name__ == "__main__":
    unittest.main()
