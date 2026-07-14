"""V2-7.2 deterministic long-window chained-continuity foundation tests."""

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from printer_v1.db import apply_migrations
from printer_v1.snapshots.cadence_policy import get_policy
from printer_v1.snapshots.lifecycle_continuity import (
    CONTINUITY_BLOCKED,
    CONTINUITY_CONTINUOUS,
    CONTINUITY_DIRTY,
    build_long_window_continuation_plan,
    compute_long_window_deadline,
    evaluate_long_window_continuity,
    resolve_current_run_long_predecessor,
    terminally_block_long_continuation,
)


T0 = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
TRANSITIONS = (
    ("WINDOW_1H", "WINDOW_4H", 10800),
    ("WINDOW_4H", "WINDOW_12H", 28800),
    ("WINDOW_12H", "WINDOW_24H", 43200),
)
LANES = ("TRACK_FAST", "TRACK_NORMAL")


def _predecessor(
    predecessor_kind: str,
    *,
    lane: str = "TRACK_FAST",
    window_id: int = 10,
) -> dict[str, object]:
    return {
        "id": window_id,
        "run_id": "run-current",
        "token_id": 1,
        "pair_id": 2,
        "tracking_lane": lane,
        "window_kind": predecessor_kind,
        "window_status": "WINDOW_CLOSED",
        "snapshot_end_id": 99,
        "closed_at": T0.isoformat(),
        "window_end_at": T0.isoformat(),
    }


def _successor(
    predecessor: dict[str, object],
    successor_kind: str,
    gap_seconds: float,
) -> dict[str, object]:
    lane = str(predecessor["tracking_lane"])
    deadline = compute_long_window_deadline(T0, successor_kind, lane)
    return {
        "run_id": predecessor["run_id"],
        "token_id": predecessor["token_id"],
        "pair_id": predecessor["pair_id"],
        "tracking_lane": lane,
        "window_kind": successor_kind,
        "continuation_of_window_id": predecessor["id"],
        "linked_closing_snapshot_id": predecessor["snapshot_end_id"],
        "linked_first_snapshot_id": 100,
        "first_snapshot_at": (T0 + timedelta(seconds=gap_seconds)).isoformat(),
        "window_end_at": deadline.isoformat(),
    }


class LongWindowPureContractTests(unittest.TestCase):
    def test_plans_derive_unchanged_policy_deadlines_counts_and_remain_disabled(self) -> None:
        for predecessor_kind, successor_kind, duration in TRANSITIONS:
            for lane in LANES:
                with self.subTest(successor=successor_kind, lane=lane):
                    predecessor = _predecessor(predecessor_kind, lane=lane)
                    plan = build_long_window_continuation_plan(predecessor, successor_kind)
                    policy = get_policy(successor_kind, lane)
                    self.assertTrue(plan["plan_ok"])
                    self.assertFalse(plan["activation_allowed"])
                    self.assertFalse(plan["enabled_for_real_collection"])
                    self.assertEqual(plan["continuation_seconds"], duration)
                    self.assertEqual(plan["expected_snapshots"], policy.minimum_required_snapshots)
                    self.assertEqual(
                        datetime.fromisoformat(str(plan["deadline_at"])),
                        T0 + timedelta(seconds=duration),
                    )
                    self.assertEqual(plan["continuation_of_window_id"], predecessor["id"])
                    self.assertEqual(plan["linked_closing_snapshot_id"], 99)

    def test_clean_dirty_and_blocked_boundaries_for_every_transition_and_lane(self) -> None:
        for predecessor_kind, successor_kind, _ in TRANSITIONS:
            for lane in LANES:
                policy = get_policy(successor_kind, lane)
                predecessor = _predecessor(predecessor_kind, lane=lane)
                cases = (
                    (policy.clean_max_gap_seconds, CONTINUITY_CONTINUOUS, False),
                    (policy.clean_max_gap_seconds + 1, CONTINUITY_DIRTY, True),
                    (policy.blocked_at_gap_seconds - 1, CONTINUITY_DIRTY, True),
                    (policy.blocked_at_gap_seconds, CONTINUITY_BLOCKED, True),
                    (policy.blocked_at_gap_seconds + 1, CONTINUITY_BLOCKED, True),
                )
                for gap, expected, do_not_train in cases:
                    with self.subTest(successor=successor_kind, lane=lane, gap=gap):
                        result = evaluate_long_window_continuity(
                            predecessor, _successor(predecessor, successor_kind, gap)
                        )
                        self.assertEqual(result.status, expected)
                        self.assertEqual(result.do_not_train, do_not_train)
                        self.assertEqual(
                            result.can_be_quality_memory,
                            expected == CONTINUITY_CONTINUOUS,
                        )

    def test_every_forbidden_linkage_or_timing_shape_blocks(self) -> None:
        predecessor = _predecessor("WINDOW_1H")
        base = _successor(predecessor, "WINDOW_4H", 1)
        mutations = {
            "manual": {"manual_linkage": True},
            "historical": {"reuses_historical_window": True},
            "consumed": {},
            "wrong_predecessor": {"window_kind": "WINDOW_12H"},
            "wrong_close_snapshot": {"linked_closing_snapshot_id": 1000},
            "wrong_run": {"run_id": "other"},
            "wrong_token": {"token_id": 8},
            "wrong_pair": {"pair_id": 9},
            "wrong_lane": {"tracking_lane": "TRACK_NORMAL"},
            "interpolation": {"interpolated_first_snapshot": True},
            "aggregation": {"aggregated_predecessor": True},
            "clock_reset": {"clock_reset": True},
            "delayed_restart": {"delayed_restart": True},
            "wrong_window_link": {"continuation_of_window_id": 77},
            "deadline_drift": {
                "window_end_at": (T0 + timedelta(seconds=10801)).isoformat()
            },
            "missing_first_snapshot": {"linked_first_snapshot_id": None},
            "missing_first_snapshot_time": {"first_snapshot_at": None},
        }
        for name, changes in mutations.items():
            with self.subTest(case=name):
                successor = dict(base)
                successor.update(changes)
                consumed = [10] if name == "consumed" else []
                result = evaluate_long_window_continuity(
                    predecessor,
                    successor,
                    consumed_predecessor_window_ids=consumed,
                )
                self.assertEqual(result.status, CONTINUITY_BLOCKED)
        negative = _successor(predecessor, "WINDOW_4H", -1)
        self.assertEqual(
            evaluate_long_window_continuity(predecessor, negative).status,
            CONTINUITY_BLOCKED,
        )

    def test_delayed_first_snapshot_never_extends_deadline(self) -> None:
        predecessor = _predecessor("WINDOW_4H", lane="TRACK_NORMAL")
        successor = _successor(predecessor, "WINDOW_12H", 700)
        successor["window_end_at"] = (
            datetime.fromisoformat(str(successor["first_snapshot_at"]))
            + timedelta(seconds=28800)
        ).isoformat()
        result = evaluate_long_window_continuity(predecessor, successor)
        self.assertEqual(result.status, CONTINUITY_BLOCKED)
        self.assertIn("deadline_target_drift", result.reasons)


class LongWindowDbFoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "continuity.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.run_id = "run-current"
        self.conn.execute(
            """INSERT INTO printer_memory_factory_runs
               (run_id,run_status,window_kind,db_mode,config_hash,config_json,started_at)
               VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','hash','{}',?)""",
            (self.run_id, T0.isoformat()),
        )
        self.token_a, self.pair_a = self._target("A" * 32, "B" * 32)
        self.token_b, self.pair_b = self._target("C" * 32, "D" * 32)
        self.conn.commit()

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _target(self, mint: str, pair: str) -> tuple[int, int]:
        token_id = int(
            self.conn.execute(
                "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_FAST')",
                (mint,),
            ).lastrowid
        )
        pair_id = int(
            self.conn.execute(
                "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
                (token_id, pair, mint),
            ).lastrowid
        )
        return token_id, pair_id

    def _snapshot(self, token_id: int, pair_id: int, at: datetime) -> int:
        return int(
            self.conn.execute(
                """INSERT INTO printer_token_snapshots
                   (token_id,pair_id,captured_at,tracking_lane,snapshot_mode,
                    price_usd,source_status,data_quality_label)
                   VALUES (?,?,?,'TRACK_FAST','TOKEN_SNAPSHOT',1,'COMPLETE','CLEAN_DATA')""",
                (token_id, pair_id, at.isoformat()),
            ).lastrowid
        )

    def _closed_predecessor(
        self,
        window_kind: str,
        *,
        run_id: str | None = None,
        token_id: int | None = None,
        pair_id: int | None = None,
    ) -> tuple[int, int]:
        token_id = token_id or self.token_a
        pair_id = pair_id or self.pair_a
        snapshot_id = self._snapshot(token_id, pair_id, T0)
        window_id = int(
            self.conn.execute(
                """INSERT INTO printer_memory_windows
                   (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                    data_quality_label,do_not_train,window_status,memory_quality_label,
                    window_start_at,window_end_at,snapshot_start_id,snapshot_end_id)
                   VALUES (?,?,?, ?,?,'DIRTY_MEMORY','CLEAN_DATA',1,
                           'WINDOW_CLOSED','DIRTY_MEMORY',?,?,?,?)""",
                (
                    token_id,
                    pair_id,
                    window_kind,
                    (T0 - timedelta(hours=1)).isoformat(),
                    T0.isoformat(),
                    (T0 - timedelta(hours=1)).isoformat(),
                    T0.isoformat(),
                    snapshot_id,
                    snapshot_id,
                ),
            ).lastrowid
        )
        step_id = int(
            self.conn.execute(
                """INSERT INTO printer_memory_factory_run_steps
                   (run_id,step_key,step_kind,step_status,token_id,pair_id,
                    tracking_lane,snapshot_id,memory_window_id)
                   VALUES (?,?, 'CONTINUATION_CLOSE','SUCCEEDED',?,?,'TRACK_FAST',?,?)""",
                (
                    run_id or self.run_id,
                    f"t{token_id}_{window_kind.lower()}_close",
                    token_id,
                    pair_id,
                    snapshot_id,
                    window_id,
                ),
            ).lastrowid
        )
        self.conn.commit()
        return window_id, step_id

    def test_resolver_uses_only_exact_terminal_current_run_predecessor(self) -> None:
        for predecessor_kind, successor_kind, _ in TRANSITIONS:
            with self.subTest(successor=successor_kind):
                self.conn.execute("DELETE FROM printer_memory_factory_run_steps")
                self.conn.execute("DELETE FROM printer_memory_windows")
                self.conn.execute("DELETE FROM printer_token_snapshots")
                window_id, _ = self._closed_predecessor(predecessor_kind)
                resolved = resolve_current_run_long_predecessor(
                    self.conn,
                    run_id=self.run_id,
                    token_id=self.token_a,
                    pair_id=self.pair_a,
                    tracking_lane="TRACK_FAST",
                    successor_kind=successor_kind,
                )
                self.assertTrue(resolved["resolved"])
                self.assertEqual(resolved["window"]["id"], window_id)
                self.assertEqual(
                    resolved["plan"]["continuation_of_window_id"], window_id
                )
                self.assertFalse(resolved["plan"]["activation_allowed"])
                historical = resolve_current_run_long_predecessor(
                    self.conn,
                    run_id="manual-or-historical-run",
                    token_id=self.token_a,
                    pair_id=self.pair_a,
                    tracking_lane="TRACK_FAST",
                    successor_kind=successor_kind,
                )
                self.assertFalse(historical["resolved"])

    def test_consumed_predecessor_cannot_reopen(self) -> None:
        window_id, _ = self._closed_predecessor("WINDOW_1H")
        self.conn.execute(
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,memory_status,
                data_quality_label,do_not_train,supporting_context_json)
               VALUES (?,?, 'WINDOW_4H', ?,'DIRTY_MEMORY','CLEAN_DATA',1,?)""",
            (
                self.token_a,
                self.pair_a,
                T0.isoformat(),
                json.dumps({"continuation_of_window_id": window_id}),
            ),
        )
        self.conn.commit()
        result = resolve_current_run_long_predecessor(
            self.conn,
            run_id=self.run_id,
            token_id=self.token_a,
            pair_id=self.pair_a,
            tracking_lane="TRACK_FAST",
            successor_kind="WINDOW_4H",
        )
        self.assertFalse(result["resolved"])
        self.assertIn("already_consumed", " ".join(result["reasons"]))

    def _pending_long_job(
        self,
        token_id: int,
        pair_id: int,
        successor_kind: str,
        key: str,
    ) -> tuple[int, int]:
        job_id = int(
            self.conn.execute(
                """INSERT INTO printer_scheduler_jobs
                   (job_name,job_kind,status,scheduled_for)
                   VALUES (?,'MEMORY_WINDOW_CLOSE','PENDING',?)""",
                (key, T0.isoformat()),
            ).lastrowid
        )
        step_id = int(
            self.conn.execute(
                """INSERT INTO printer_memory_factory_run_steps
                   (run_id,step_key,step_kind,step_status,token_id,pair_id,
                    tracking_lane,scheduler_job_id,result_json)
                   VALUES (?,?, 'LONG_CONTINUATION_SNAPSHOT','PENDING',?,?,'TRACK_FAST',?,?)""",
                (
                    self.run_id,
                    key,
                    token_id,
                    pair_id,
                    job_id,
                    json.dumps({"successor_window_kind": successor_kind}),
                ),
            ).lastrowid
        )
        return step_id, job_id

    def test_block_is_token_local_and_replay_never_retries(self) -> None:
        a_4h, a_4h_job = self._pending_long_job(
            self.token_a, self.pair_a, "WINDOW_4H", "a_4h"
        )
        a_12h, _ = self._pending_long_job(
            self.token_a, self.pair_a, "WINDOW_12H", "a_12h"
        )
        b_4h, b_4h_job = self._pending_long_job(
            self.token_b, self.pair_b, "WINDOW_4H", "b_4h"
        )
        self.conn.commit()
        first = terminally_block_long_continuation(
            self.conn,
            run_id=self.run_id,
            token_id=self.token_a,
            pair_id=self.pair_a,
            tracking_lane="TRACK_FAST",
            successor_kind="WINDOW_4H",
            reason="CONTINUITY_BLOCKED",
        )
        self.conn.commit()
        second = terminally_block_long_continuation(
            self.conn,
            run_id=self.run_id,
            token_id=self.token_a,
            pair_id=self.pair_a,
            tracking_lane="TRACK_FAST",
            successor_kind="WINDOW_4H",
            reason="CONTINUITY_BLOCKED",
        )
        self.conn.commit()
        self.assertEqual(first["cancelled_jobs"], 1)
        self.assertTrue(second["already_terminal"])
        self.assertEqual(second["cancelled_jobs"], 0)
        statuses = dict(
            self.conn.execute(
                "SELECT id,step_status FROM printer_memory_factory_run_steps WHERE id IN (?,?,?)",
                (a_4h, a_12h, b_4h),
            ).fetchall()
        )
        self.assertEqual(statuses[a_4h], "CANCELLED")
        self.assertEqual(statuses[a_12h], "PENDING")
        self.assertEqual(statuses[b_4h], "PENDING")
        jobs = dict(
            self.conn.execute(
                "SELECT id,status FROM printer_scheduler_jobs WHERE id IN (?,?)",
                (a_4h_job, b_4h_job),
            ).fetchall()
        )
        self.assertEqual(jobs[a_4h_job], "CANCELLED")
        self.assertEqual(jobs[b_4h_job], "PENDING")
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_memory_factory_run_steps "
                "WHERE step_kind='LONG_CONTINUITY_BLOCK'"
            ).fetchone()[0],
            1,
        )
        self.assertEqual(
            self.conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows "
                "WHERE window_kind IN ('WINDOW_4H','WINDOW_12H','WINDOW_24H')"
            ).fetchone()[0],
            0,
        )

    def test_downstream_locks_remain_zero(self) -> None:
        tables = (
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        )
        for table in tables:
            with self.subTest(table=table):
                self.assertEqual(
                    self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0],
                    0,
                )


if __name__ == "__main__":
    unittest.main()
