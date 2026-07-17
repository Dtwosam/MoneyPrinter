"""V2-9.4.8 -- 15m close ordering and exact-ledger attachment.

The 15m close previously resolved shared context BEFORE the closing snapshot was
attached to the current-run ledger. The V2-9.4.6 exact-ledger resolver cannot
operate in that order: the ledger intersection would not see the closing
snapshot and would report a false SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER.

Required order (proved below):
  1. capture and persist the closing snapshot
  2. attach the exact closing snapshot_id to the current-run ledger
  3. verify the closing snapshot belongs to this exact run, token and pair
  4. resolve shared context using the exact ledger snapshot range
  5. run E2Q, Lane Q and Lane K/E2Z
  6. finalize the close step and memory window

The 4h path already had the correct order and is unchanged.

Paper-only. Temporary isolated DBs only. No live sources, no retrieval,
no financial deltas.
"""

import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT / "tests"))

import test_v2_4_one_command_15m_factory as v24  # noqa: E402  (shared harness)

from printer_v1.context_evidence import build_window_15m_context_evidence  # noqa: E402
from printer_v1.db import apply_migrations  # noqa: E402
from printer_v1.operator_cli.one_command_15m_factory import (  # noqa: E402
    _attach_closing_snapshot_to_ledger,
)
from printer_v1.snapshots.recorder import record_token_snapshot  # noqa: E402

RUN_ID = "v2-9-4-8-run"
OTHER_RUN_ID = "some-other-run"


class Close15mLedgerOrderingTest(unittest.TestCase):
    """Integration: drive the real 15m factory close through _execute_close.

    The harness helpers are borrowed by reference from the V2-4 suite rather
    than subclassed, so the V2-4 tests are not re-collected here.
    """

    setUp = v24.OneCommand15mFactoryTests.setUp
    tearDown = v24.OneCommand15mFactoryTests.tearDown
    _discovery = v24.OneCommand15mFactoryTests._discovery
    _adapter_factory = v24.OneCommand15mFactoryTests._adapter_factory
    _failing_context_factories = v24.OneCommand15mFactoryTests._failing_context_factories
    _clean_context_factories = v24.OneCommand15mFactoryTests._clean_context_factories
    _run = v24.OneCommand15mFactoryTests._run

    def _close_step(self, result):
        return next(s for s in result["steps"] if s["step_kind"] == "WINDOW_CLOSE")

    def _ledger_snapshot_ids(self, run_id):
        conn = sqlite3.connect(self.db)
        try:
            return {
                int(r[0]) for r in conn.execute(
                    "SELECT snapshot_id FROM printer_memory_factory_run_steps"
                    " WHERE run_id=? AND snapshot_id IS NOT NULL",
                    (run_id,),
                ).fetchall()
            }
        finally:
            conn.close()

    def _count(self, table, where="", params=()):
        conn = sqlite3.connect(self.db)
        try:
            exists = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
            if exists is None:
                return None
            sql = f"SELECT COUNT(*) FROM {table}" + (f" WHERE {where}" if where else "")
            return int(conn.execute(sql, params).fetchone()[0])
        finally:
            conn.close()

    # --- 1 + 2. ledger attachment happens BEFORE context resolution --------

    def test_closing_snapshot_is_in_the_ledger_before_context_resolution(self):
        """The ordering proof: inspect the ledger at the moment the resolver runs."""
        observed = {}

        def spy(connection, **kwargs):
            # Read the ledger through the resolver's own connection, at the
            # exact moment shared-context resolution begins.
            rows = {
                int(r[0]) for r in connection.execute(
                    "SELECT snapshot_id FROM printer_memory_factory_run_steps"
                    " WHERE run_id=? AND snapshot_id IS NOT NULL",
                    (kwargs["run_id"],),
                ).fetchall()
            }
            observed["run_id"] = kwargs["run_id"]
            observed["snapshot_end_id"] = kwargs["snapshot_end_id"]
            observed["snapshot_start_id"] = kwargs["snapshot_start_id"]
            observed["closing_in_ledger_at_resolve_time"] = kwargs["snapshot_end_id"] in rows
            observed["ledger_ids"] = rows
            observed["tracking_lane_passed"] = "tracking_lane" in kwargs
            return {
                "clean_memory_context_ready": False,
                "blockers": ["FIXTURE_SHORT_CIRCUIT"],
                "sections": {},
                "writes_performed": False,
            }

        with patch(
            "printer_v1.context_evidence.build_window_15m_context_evidence",
            side_effect=spy,
        ):
            result, _calls = self._run()

        close = self._close_step(result)
        # 1. The closing snapshot was already ledger-attached when the resolver ran.
        self.assertTrue(
            observed["closing_in_ledger_at_resolve_time"],
            "closing snapshot must be attached to the current-run ledger before"
            " shared context resolution begins",
        )
        # 2. The exact ledger range includes the closing snapshot.
        self.assertEqual(observed["snapshot_end_id"], close["snapshot_id"])
        self.assertIn(close["snapshot_id"], observed["ledger_ids"])
        self.assertEqual(observed["run_id"], close["run_id"])
        self.assertIn(observed["snapshot_start_id"], observed["ledger_ids"])

    def test_15m_closing_lateness_allowance_is_not_widened(self):
        """tracking_lane must not be passed: it would widen 0s lateness to 60s."""
        seen = {}

        def spy(connection, **kwargs):
            seen.update(kwargs)
            return {
                "clean_memory_context_ready": False,
                "blockers": ["FIXTURE_SHORT_CIRCUIT"],
                "sections": {},
                "writes_performed": False,
            }

        with patch(
            "printer_v1.context_evidence.build_window_15m_context_evidence",
            side_effect=spy,
        ):
            self._run()
        self.assertIn("run_id", seen)
        self.assertNotIn(
            "tracking_lane", seen,
            "passing tracking_lane would silently widen the 15m closing-lateness"
            " contract from 0s to the 4h 60s allowance",
        )

    # --- 5. a valid close attaches honestly and leaves the ledger exact -----

    def test_valid_close_attaches_the_exact_closing_snapshot(self):
        """The close reports its attachment honestly and the ledger is exact.

        This harness compresses the window to fractions of a second, so the real
        resolver rejects it on the 900s minimum span before the ledger
        intersection is ever reached. Asserting the absence of
        SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER here would therefore be vacuous --
        that proof lives in Exact15mLedgerRangeTest, which uses a genuine
        15-minute window.
        """
        import json

        result, _calls = self._run(
            context_adapter_factories=self._clean_context_factories()
        )
        close = self._close_step(result)
        close_result = json.loads(close["result_json"])
        self.assertTrue(close_result["ok"], close_result.get("blocked_reason"))
        attachment = close_result["ledger_attachment"]
        self.assertTrue(attachment["attached"])
        self.assertEqual(attachment["snapshot_id"], close["snapshot_id"])
        self.assertEqual(attachment["run_id"], close["run_id"])
        self.assertEqual(attachment["token_id"], close["token_id"])
        self.assertEqual(attachment["pair_id"], close["pair_id"])
        # The ledger holds the exact closing snapshot for this run.
        self.assertIn(close["snapshot_id"], self._ledger_snapshot_ids(close["run_id"]))
        # Context resolution did run and reported through to the audit.
        self.assertIn("context_quality", close_result)

    # --- 10. no retrieval or financial deltas ------------------------------

    def test_close_creates_no_retrieval_or_financial_deltas(self):
        result, _calls = self._run()
        for table in (
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        ):
            count = self._count(table)
            if count is not None:
                self.assertEqual(count, 0, table)

    # --- 7. replay / idempotency -------------------------------------------

    def test_attachment_is_idempotent_and_creates_no_duplicates(self):
        result, _calls = self._run()
        close = self._close_step(result)
        run_id = close["run_id"]
        before_steps = self._count(
            "printer_memory_factory_run_steps", "run_id=?", (run_id,)
        )
        before_snapshots = self._count("printer_token_snapshots")
        before_windows = self._count("printer_memory_windows")
        before_ledger = self._ledger_snapshot_ids(run_id)

        # Replay the attachment against the same close step: it must be a no-op.
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            step = conn.execute(
                "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
                (close["id"],),
            ).fetchone()
            for _ in range(2):
                report = _attach_closing_snapshot_to_ledger(
                    conn, step=step, result={"snapshot_id": close["snapshot_id"]}
                )
                # Already-finalized steps are not RUNNING, but the ledger already
                # holds the exact snapshot, so attachment confirms rather than fails.
                self.assertTrue(report["attached"])
                self.assertEqual(report["snapshot_id"], close["snapshot_id"])
        finally:
            conn.close()

        self.assertEqual(
            self._count("printer_memory_factory_run_steps", "run_id=?", (run_id,)),
            before_steps,
        )
        self.assertEqual(self._count("printer_token_snapshots"), before_snapshots)
        self.assertEqual(self._count("printer_memory_windows"), before_windows)
        self.assertEqual(self._ledger_snapshot_ids(run_id), before_ledger)

    def test_wrong_token_or_pair_identity_fails_closed_with_precise_reason(self):
        result, _calls = self._run()
        close = self._close_step(result)
        conn = sqlite3.connect(self.db)
        conn.row_factory = sqlite3.Row
        try:
            step = conn.execute(
                "SELECT * FROM printer_memory_factory_run_steps WHERE id=?",
                (close["id"],),
            ).fetchone()
            # A snapshot belonging to a different token/pair must never attach.
            other_token = int(
                conn.execute(
                    "INSERT INTO printer_tokens(token_mint,chain) VALUES ('other-mint','solana')"
                ).lastrowid
            )
            other_pair = int(
                conn.execute(
                    "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint)"
                    " VALUES (?,'other-pair','other-mint')",
                    (other_token,),
                ).lastrowid
            )
            foreign_snapshot = int(
                conn.execute(
                    """INSERT INTO printer_token_snapshots
                       (token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                        price_usd,liquidity_usd,source_status,data_quality_label)
                       VALUES (?,?,?,'TRACK_FAST','NORMAL_MODE',1.0,1000,'COMPLETE','CLEAN_DATA')""",
                    (other_token, other_pair, datetime.now(timezone.utc).isoformat()),
                ).lastrowid
            )
            conn.commit()
            report = _attach_closing_snapshot_to_ledger(
                conn, step=step, result={"snapshot_id": foreign_snapshot}
            )
            self.assertFalse(report["attached"])
            self.assertEqual(report["reason"], "CLOSING_SNAPSHOT_TARGET_MISMATCH")

            missing = _attach_closing_snapshot_to_ledger(
                conn, step=step, result={"snapshot_id": 10_000_000}
            )
            self.assertFalse(missing["attached"])
            self.assertEqual(missing["reason"], "CLOSING_SNAPSHOT_NOT_PERSISTED")
        finally:
            conn.close()


class Exact15mLedgerRangeTest(unittest.TestCase):
    """Resolver-level: the 15m exact-ledger range excludes everything foreign."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "ordering.sqlite3"
        apply_migrations(self.db_path)
        self.start = datetime(2026, 7, 13, 12, 0, tzinfo=timezone.utc)
        self.end = self.start + timedelta(minutes=15)
        with self.connect() as conn:
            self.token_id = int(
                conn.execute(
                    "INSERT INTO printer_tokens(token_mint,chain) VALUES ('m','solana')"
                ).lastrowid
            )
            self.pair_id = int(
                conn.execute(
                    "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint)"
                    " VALUES (?,'p','m')",
                    (self.token_id,),
                ).lastrowid
            )
            self.other_token_id = int(
                conn.execute(
                    "INSERT INTO printer_tokens(token_mint,chain) VALUES ('m2','solana')"
                ).lastrowid
            )
            self.other_pair_id = int(
                conn.execute(
                    "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint)"
                    " VALUES (?,'p2','m2')",
                    (self.other_token_id,),
                ).lastrowid
            )
        self.request_id, self.response_id = self.trace()

    def tearDown(self):
        self.tempdir.cleanup()

    def connect(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        class _Ctx:
            def __enter__(_s):
                return conn

            def __exit__(_s, *_a):
                conn.commit()
                conn.close()

        return _Ctx()

    def trace(self):
        with self.connect() as conn:
            rq = int(
                conn.execute(
                    """INSERT INTO printer_source_requests
                       (source_name,request_kind,requested_at,source_status,data_quality_label)
                       VALUES ('dexscreener','pair_market_snapshot',?,'COMPLETE','CLEAN_DATA')""",
                    (self.start.isoformat(),),
                ).lastrowid
            )
            rs = int(
                conn.execute(
                    """INSERT INTO printer_source_responses
                       (source_request_id,source_name,received_at,source_status,
                        data_quality_label,normalized_payload_json)
                       VALUES (?,'dexscreener',?,'COMPLETE','CLEAN_DATA','{}')""",
                    (rq, self.start.isoformat()),
                ).lastrowid
            )
        return rq, rs

    def snapshot(self, captured_at, *, token_id=None, pair_id=None, index=0):
        payload = {
            "token_id": self.token_id if token_id is None else token_id,
            "pair_id": self.pair_id if pair_id is None else pair_id,
            "token_mint": "m",
            "pair_address": "p",
            "captured_at": captured_at.isoformat(),
            "tracking_lane": "TRACK_FAST",
            "snapshot_mode": "NORMAL_MODE",
            "price_usd": 1.0 + index * 0.01,
            "liquidity_usd": 100_000,
            "volume_5m": 30_000,
            "txns_5m": 60,
            "buys_5m": 40,
            "sells_5m": 20,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "source_name": "dexscreener",
            "source_request_id": self.request_id,
            "source_response_id": self.response_id,
        }
        _created, sid = record_token_snapshot(self.db_path, payload, captured_at)
        return int(sid)

    def ledger(self, snapshot_ids, *, run_id=RUN_ID):
        with self.connect() as conn:
            for i, sid in enumerate(snapshot_ids):
                conn.execute(
                    """INSERT INTO printer_memory_factory_run_steps
                       (run_id,step_key,step_kind,step_status,token_id,pair_id,
                        tracking_lane,snapshot_id,created_at,updated_at)
                       VALUES (?,?,?,?,?,?, 'TRACK_FAST',?,?,?)""",
                    (
                        run_id, f"s{i}",
                        "WINDOW_CLOSE" if sid == snapshot_ids[-1] else "SNAPSHOT",
                        "RUNNING" if sid == snapshot_ids[-1] else "SUCCEEDED",
                        self.token_id, self.pair_id, sid,
                        self.start.isoformat(), self.start.isoformat(),
                    ),
                )

    def window(self):
        """Predecessor exactly at window_start_at, then the real ledger window."""
        predecessor = self.snapshot(self.start, index=0)
        ids = [self.snapshot(self.start + timedelta(minutes=3 * (i + 1)), index=i + 1) for i in range(5)]
        return predecessor, ids

    def report(self, ids, *, run_id=RUN_ID):
        with self.connect() as conn:
            before = conn.total_changes
            result = build_window_15m_context_evidence(
                conn,
                token_id=self.token_id,
                pair_id=self.pair_id,
                snapshot_start_id=ids[0],
                snapshot_end_id=ids[-1],
                window_start_at=self.start,
                window_end_at=self.end,
                run_id=run_id,
            )
            self.assertEqual(conn.total_changes, before)
        return result

    # --- 3. predecessor at exactly window_start_at is excluded -------------

    def test_predecessor_at_window_start_is_excluded(self):
        predecessor, ids = self.window()
        self.ledger(ids)
        result = self.report(ids)
        self.assertEqual(result["snapshot_ids"], ids)
        self.assertNotIn(predecessor, result["snapshot_ids"])

    # --- 4. future / unrelated-run / wrong-token / wrong-pair excluded -----

    def test_future_unrelated_wrong_token_and_wrong_pair_are_excluded(self):
        _predecessor, ids = self.window()
        self.ledger(ids)
        future = self.snapshot(self.end + timedelta(minutes=5), index=99)
        wrong_token = self.snapshot(
            self.start + timedelta(minutes=4),
            token_id=self.other_token_id, pair_id=self.other_pair_id, index=99,
        )
        result = self.report(ids)
        self.assertEqual(result["snapshot_ids"], ids)
        self.assertNotIn(future, result["snapshot_ids"])
        self.assertNotIn(wrong_token, result["snapshot_ids"])

    def test_snapshot_from_another_run_is_specifically_blocked(self):
        _predecessor, ids = self.window()
        self.ledger(ids[:-1])
        self.ledger([ids[-1]], run_id=OTHER_RUN_ID)
        result = self.report(ids)
        self.assertIn("SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER", result["blockers"])
        self.assertEqual(result["non_ledger_snapshot_ids"], [ids[-1]])
        self.assertFalse(result["clean_memory_context_ready"])

    # --- 5. no false ledger blocker for a correctly attached window --------

    def test_correctly_attached_window_has_no_false_ledger_blocker(self):
        _predecessor, ids = self.window()
        self.ledger(ids)
        result = self.report(ids)
        self.assertNotIn("SNAPSHOT_SET_NOT_CURRENT_RUN_LEDGER", result["blockers"])
        self.assertEqual(result["non_ledger_snapshot_ids"], [])
        self.assertNotIn("SNAPSHOT_BOUNDARY_MISMATCH", result["blockers"])

    # --- 8. the 15m closing-lateness contract is unchanged -----------------

    def test_15m_allowance_stays_zero_without_tracking_lane(self):
        _predecessor, ids = self.window()
        self.ledger(ids)
        result = self.report(ids)
        self.assertEqual(result["closing_evidence_allowance_seconds"], 0)
        self.assertEqual(result["closing_evidence_cutoff_at"], result["window_end_at"])
        self.assertEqual(result["window_end_at"], self.end.isoformat())

    # --- 12. missing/unsupported evidence still fails closed ---------------

    def test_missing_evidence_still_fails_closed(self):
        _predecessor, ids = self.window()
        self.ledger(ids)
        result = self.report(ids)
        # No safety/quote/broad context was attached, so the window must not be
        # clean. The ordering repair does not weaken any evidence gate.
        self.assertFalse(result["clean_memory_context_ready"])
        self.assertTrue(result["blockers"])
        self.assertFalse(any(result["downstream_unlocks"].values()))


if __name__ == "__main__":
    unittest.main()
