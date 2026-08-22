"""V2-7 continuous first-hour readiness checks (temporary DBs only)."""

from __future__ import annotations

import json
import shutil
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import (
    _cancel_pending_for_token,
    _capture_same_stream_5m_support,
    _plan_continuation_jobs,
    _resolve_current_run_15m_source,
)


MINT_A = "A" * 32
PAIR_A = "B" * 32
MINT_B = "C" * 32
PAIR_B = "D" * 32


class ContinuousFirstHourReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "proof.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.now = datetime.now(timezone.utc)
        self.run_id = "v2-7-readiness"
        self.conn.execute(
            """INSERT INTO printer_memory_factory_runs
               (run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at)
               VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','hash',?,?)""",
            (self.run_id, json.dumps({"continuous_first_hour": True}), self.now.isoformat()),
        )
        self.token_a, self.pair_a = self._target(MINT_A, PAIR_A)
        self.token_b, self.pair_b = self._target(MINT_B, PAIR_B)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _target(self, mint: str, pair: str) -> tuple[int, int]:
        token_id = int(self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_FAST')",
            (mint,),
        ).lastrowid)
        pair_id = int(self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (token_id, pair, mint),
        ).lastrowid)
        return token_id, pair_id

    def _snapshot(self, token_id: int, pair_id: int, captured_at: datetime) -> int:
        return int(self.conn.execute(
            """INSERT INTO printer_token_snapshots
               (token_id,pair_id,captured_at,tracking_lane,snapshot_mode,price_usd,
                source_status,data_quality_label)
               VALUES (?,?,?,'TRACK_FAST','TOKEN_SNAPSHOT',1.0,'COMPLETE','CLEAN_DATA')""",
            (token_id, pair_id, captured_at.isoformat()),
        ).lastrowid)

    def _closed_15m(self, *, run_id: str | None = None, status: str = "SUCCEEDED") -> tuple[int, int]:
        start_id = self._snapshot(self.token_a, self.pair_a, self.now)
        end_at = self.now + timedelta(seconds=900)
        end_id = self._snapshot(self.token_a, self.pair_a, end_at)
        window_id = int(self.conn.execute(
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                data_quality_label,do_not_train,window_status,memory_quality_label,
                window_start_at,window_end_at,snapshot_start_id,snapshot_end_id)
               VALUES (?,?, 'WINDOW_15M', ?,?,'DIRTY_MEMORY','CLEAN_DATA',1,
                       'WINDOW_CLOSED','DIRTY_MEMORY',?,?,?,?)""",
            (self.token_a, self.pair_a, self.now.isoformat(), end_at.isoformat(),
             self.now.isoformat(), end_at.isoformat(), start_id, end_id),
        ).lastrowid)
        step_id = int(self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,snapshot_id,memory_window_id)
               VALUES (?,'t1_window_close','WINDOW_CLOSE',?,?,?,?,?,'TRACK_FAST',?,?)""",
            (run_id or self.run_id, status, self.token_a, self.pair_a, MINT_A, PAIR_A,
             end_id, window_id),
        ).lastrowid)
        self.conn.commit()
        return window_id, step_id

    def test_exact_current_running_close_resolves_but_manual_or_historical_does_not(self) -> None:
        window_id, step_id = self._closed_15m(status="RUNNING")
        resolved = _resolve_current_run_15m_source(
            self.conn, run_id=self.run_id, token_id=self.token_a, pair_id=self.pair_a,
            tracking_lane="TRACK_FAST", current_close_step_id=step_id,
        )
        self.assertTrue(resolved["resolved"])
        self.assertEqual(int(resolved["window"]["id"]), window_id)
        blocked = _resolve_current_run_15m_source(
            self.conn, run_id="operator-supplied-history", token_id=self.token_a,
            pair_id=self.pair_a, tracking_lane="TRACK_FAST",
            current_close_step_id=step_id,
        )
        self.assertFalse(blocked["resolved"])

    def test_consumed_15m_window_is_rejected(self) -> None:
        window_id, _ = self._closed_15m()
        self.conn.execute(
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                data_quality_label,do_not_train,supporting_context_json)
               VALUES (?,?, 'WINDOW_1H', ?,?,'DIRTY_MEMORY','CLEAN_DATA',1,?)""",
            (self.token_a, self.pair_a, self.now.isoformat(),
             (self.now + timedelta(seconds=3600)).isoformat(),
             json.dumps({"continuation_of_window_id": window_id})),
        )
        self.conn.commit()
        result = _resolve_current_run_15m_source(
            self.conn, run_id=self.run_id, token_id=self.token_a, pair_id=self.pair_a,
            tracking_lane="TRACK_FAST",
        )
        self.assertFalse(result["resolved"])
        self.assertIn("already_consumed", " ".join(result["reasons"]))

    def test_fixed_deadline_and_fast_normal_counts(self) -> None:
        window_id, step_id = self._closed_15m()
        step = self.conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE id=?", (step_id,),
        ).fetchone()
        source = _resolve_current_run_15m_source(
            self.conn, run_id=self.run_id, token_id=self.token_a, pair_id=self.pair_a,
            tracking_lane="TRACK_FAST",
        )["window"]
        plan = _plan_continuation_jobs(
            self.conn, run_id=self.run_id, close_step=step, fifteen_m=source,
            continuation_seconds=2700,
        )
        self.conn.commit()
        self.assertTrue(plan["enqueue_ok"])
        self.assertEqual(plan["expected_snapshots"], 24)
        close = self.conn.execute(
            "SELECT scheduled_for FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind='CONTINUATION_CLOSE_EVIDENCE'",
            (self.run_id,),
        ).fetchone()
        expected = datetime.fromisoformat(source["closed_at"]) + timedelta(seconds=2700)
        self.assertEqual(datetime.fromisoformat(close[0]), expected)
        self.assertEqual(int(source["id"]), window_id)
        phases = self.conn.execute(
            """SELECT step_kind FROM printer_memory_factory_run_steps
               WHERE run_id=? AND step_kind LIKE 'CONTINUATION_CLOSE_%'
               ORDER BY id""",
            (self.run_id,),
        ).fetchall()
        self.assertEqual(
            [str(row[0]) for row in phases],
            [
                "CONTINUATION_CLOSE_EVIDENCE",
                "CONTINUATION_CLOSE_CONTEXT",
                "CONTINUATION_CLOSE_AUDIT",
            ],
        )

    def test_same_stream_5m_support_uses_exact_boundaries(self) -> None:
        window_id, step_id = self._closed_15m()
        for seconds in (60, 120, 180, 240, 300, 360, 420, 480, 540, 600, 660, 720, 780, 840):
            snapshot_id = self._snapshot(self.token_a, self.pair_a, self.now + timedelta(seconds=seconds))
            self.conn.execute(
                """INSERT INTO printer_memory_factory_run_steps
                   (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                    pair_address,tracking_lane,snapshot_id)
                   VALUES (?,?, 'SNAPSHOT','SUCCEEDED',?,?,?,?, 'TRACK_FAST',?)""",
                (self.run_id, f"t1_snapshot_{seconds}", self.token_a, self.pair_a,
                 MINT_A, PAIR_A, snapshot_id),
            )
        first = self.conn.execute(
            "SELECT id FROM printer_token_snapshots WHERE token_id=? ORDER BY captured_at LIMIT 1",
            (self.token_a,),
        ).fetchone()[0]
        self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,snapshot_id)
               VALUES (?,'t1_snapshot_00','SNAPSHOT','SUCCEEDED',?,?,?,?, 'TRACK_FAST',?)""",
            (self.run_id, self.token_a, self.pair_a, MINT_A, PAIR_A, first),
        )
        self.conn.commit()
        close_step = self.conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE id=?", (step_id,),
        ).fetchone()
        result = _capture_same_stream_5m_support(
            self.conn, run_id=self.run_id, close_step=close_step,
            parent_window_id=window_id,
        )
        self.assertIsNotNone(result["window_5m_id"])
        self.assertEqual(result["snapshot_start_id"], first)
        end_at = self.conn.execute(
            "SELECT captured_at FROM printer_token_snapshots WHERE id=?",
            (result["snapshot_end_id"],),
        ).fetchone()[0]
        self.assertLessEqual(
            (datetime.fromisoformat(end_at) - self.now).total_seconds(), 300,
        )

    def test_terminal_cancel_is_token_local(self) -> None:
        for token_id, pair_id, mint, pair in (
            (self.token_a, self.pair_a, MINT_A, PAIR_A),
            (self.token_b, self.pair_b, MINT_B, PAIR_B),
        ):
            target = {"token_id": token_id, "pair_id": pair_id, "token_mint": mint,
                      "pair_address": pair, "tracking_lane": "TRACK_FAST"}
            from printer_v1.operator_cli.one_command_15m_factory import _insert_step_and_job
            _insert_step_and_job(
                self.conn, run_id=self.run_id, target=target,
                step_key=f"t{token_id}_continuation_snapshot_00",
                step_kind="CONTINUATION_SNAPSHOT", scheduled_for=self.now,
            )
        self.conn.commit()
        cancelled = _cancel_pending_for_token(
            self.conn, self.run_id, self.token_a, "CONTINUITY_BLOCKED",
        )
        self.conn.commit()
        self.assertEqual(cancelled, 1)
        statuses = dict(self.conn.execute(
            "SELECT token_id,step_status FROM printer_memory_factory_run_steps"
        ).fetchall())
        self.assertEqual(statuses[self.token_a], "CANCELLED")
        self.assertEqual(statuses[self.token_b], "PENDING")


if __name__ == "__main__":
    unittest.main()
