"""V2-8.1 deterministic one-token 1h-to-4h runtime verification."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli import one_command_15m_factory as factory
from printer_v1.operator_cli.one_token_4h_runtime import (
    FourHourExecutionAuthority,
    close_current_run_4h,
    plan_current_run_4h,
    run_4h_quality_gates,
    runtime_budget,
)
from printer_v1.snapshots.cadence_policy import get_policy


T0 = datetime(2026, 7, 14, 12, 0, tzinfo=timezone.utc)
MINT = "A" * 32
PAIR = "B" * 32


class OneToken4hRuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.db = Path(self.temp.name) / "proof.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _foundation(self, lane: str = "TRACK_FAST") -> tuple[str, int, int, int, int]:
        run_id = f"run-{lane.lower()}"
        self.conn.execute(
            """INSERT INTO printer_memory_factory_runs
               (run_id,run_status,window_kind,db_mode,config_hash,config_json,
                selected_token_count,started_at)
               VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','hash',?,1,?)""",
            (run_id, json.dumps({"continuous_first_hour": True, "continuous_four_hour": True}), T0.isoformat()),
        )
        token_id = int(self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana',?)",
            (MINT, lane),
        ).lastrowid)
        pair_id = int(self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (token_id, PAIR, MINT),
        ).lastrowid)
        close_snapshot = self._snapshot(token_id, pair_id, lane, T0)
        predecessor_id = int(self.conn.execute(
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                memory_quality_label,data_quality_label,do_not_train,window_status,
                supporting_context_json,window_start_at,window_end_at,
                snapshot_start_id,snapshot_end_id)
               VALUES (?,?, 'WINDOW_1H', ?,?,'PARTIAL_MEMORY','PARTIAL_MEMORY',
                       'CLEAN_DATA',0,'WINDOW_CLOSED','{}',?,?,?,?)""",
            (
                token_id, pair_id, (T0 - timedelta(seconds=2700)).isoformat(),
                T0.isoformat(), (T0 - timedelta(seconds=2700)).isoformat(),
                T0.isoformat(), close_snapshot, close_snapshot,
            ),
        ).lastrowid)
        close_step = int(self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,snapshot_id,memory_window_id)
               VALUES (?,'t1_continuation_close','CONTINUATION_CLOSE','SUCCEEDED',
                       ?,?,?,?,?,?,?)""",
            (run_id, token_id, pair_id, MINT, PAIR, lane, close_snapshot, predecessor_id),
        ).lastrowid)
        self.conn.commit()
        return run_id, token_id, pair_id, predecessor_id, close_step

    def _snapshot(self, token_id: int, pair_id: int, lane: str, at: datetime) -> int:
        return int(self.conn.execute(
            """INSERT INTO printer_token_snapshots
               (token_id,pair_id,captured_at,tracking_lane,snapshot_mode,price_usd,
                liquidity_usd,volume_5m,volume_1h,txns_5m,txns_1h,
                source_status,data_quality_label)
               VALUES (?,?,?,?,'TOKEN_SNAPSHOT',1,10000,100,1000,5,25,
                       'COMPLETE','CLEAN_DATA')""",
            (token_id, pair_id, at.isoformat(), lane),
        ).lastrowid)

    def test_budget_and_plans_are_exact_and_real_collection_is_explicit(self) -> None:
        for lane, expected, interval, requests, scheduler in (
            ("TRACK_FAST", 61, 180, 69, 64),
            ("TRACK_NORMAL", 31, 360, 39, 34),
        ):
            with self.subTest(lane=lane):
                budget = runtime_budget(lane)
                self.assertEqual(budget["expected_snapshots"], expected)
                self.assertEqual(budget["snapshot_interval_seconds"], interval)
                self.assertEqual(budget["full_run_request_ceiling"], requests)
                self.assertEqual(budget["full_run_scheduler_ceiling"], scheduler)
                self.assertFalse(budget["enabled_for_real_collection"])

    def test_current_run_plan_is_exact_fixed_and_replay_safe(self) -> None:
        run_id, token_id, pair_id, predecessor_id, _ = self._foundation()
        blocked = plan_current_run_4h(
            self.conn, run_id=run_id, token_id=token_id, pair_id=pair_id,
            token_mint=MINT, pair_address=PAIR, tracking_lane="TRACK_FAST",
        )
        self.assertFalse(blocked["planned"])
        result = plan_current_run_4h(
            self.conn, run_id=run_id, token_id=token_id, pair_id=pair_id,
            token_mint=MINT, pair_address=PAIR, tracking_lane="TRACK_FAST",
            explicit_proof_mode=True,
        )
        self.conn.commit()
        self.assertTrue(result["planned"])
        self.assertEqual(result["predecessor_window_id"], predecessor_id)
        self.assertEqual(result["planned_jobs"], 63)
        self.assertEqual(datetime.fromisoformat(result["deadline_at"]), T0 + timedelta(seconds=10800))
        rows = self.conn.execute(
            "SELECT step_kind,scheduled_for FROM printer_memory_factory_run_steps "
            "WHERE run_id=? AND step_kind LIKE 'LONG_CONTINUATION_%' ORDER BY scheduled_for,id",
            (run_id,),
        ).fetchall()
        self.assertEqual(len(rows), 63)
        self.assertEqual(rows[-1]["step_kind"], "LONG_CONTINUATION_CLOSE_AUDIT")
        self.assertEqual(
            {str(row["step_kind"]) for row in rows[-3:]},
            {
                "LONG_CONTINUATION_CLOSE_EVIDENCE",
                "LONG_CONTINUATION_CLOSE_CONTEXT",
                "LONG_CONTINUATION_CLOSE_AUDIT",
            },
        )
        replay = plan_current_run_4h(
            self.conn, run_id=run_id, token_id=token_id, pair_id=pair_id,
            token_mint=MINT, pair_address=PAIR, tracking_lane="TRACK_FAST",
            explicit_proof_mode=True,
        )
        self.assertTrue(replay["replay"])
        self.assertEqual(replay["planned_jobs"], 63)

    def test_partial_replay_plan_stops_safely(self) -> None:
        run_id, token_id, pair_id, _, _ = self._foundation()
        self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane)
               VALUES (?,'partial_4h','LONG_CONTINUATION_SNAPSHOT','PENDING',?,?,?,?,?)""",
            (run_id, token_id, pair_id, MINT, PAIR, "TRACK_FAST"),
        )
        self.conn.commit()
        result = plan_current_run_4h(
            self.conn, run_id=run_id, token_id=token_id, pair_id=pair_id,
            token_mint=MINT, pair_address=PAIR, tracking_lane="TRACK_FAST",
            explicit_proof_mode=True,
        )
        self.assertFalse(result["planned"])
        self.assertEqual(
            result["blocked_reasons"],
            ["partial_or_ambiguous_4h_plan_requires_safe_stop"],
        )

    def test_wrong_run_or_consumed_predecessor_is_rejected(self) -> None:
        run_id, token_id, pair_id, predecessor_id, _ = self._foundation()
        wrong = plan_current_run_4h(
            self.conn, run_id="other", token_id=token_id, pair_id=pair_id,
            token_mint=MINT, pair_address=PAIR, tracking_lane="TRACK_FAST",
            explicit_proof_mode=True,
        )
        self.assertFalse(wrong["planned"])
        self.conn.execute(
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,
                data_quality_label,do_not_train,supporting_context_json)
               VALUES (?,?, 'WINDOW_4H', ?,?,'DIRTY_MEMORY','DIRTY_DATA',1,?)""",
            (token_id, pair_id, T0.isoformat(), T0.isoformat(), json.dumps({"continuation_of_window_id": predecessor_id})),
        )
        self.conn.commit()
        consumed = plan_current_run_4h(
            self.conn, run_id=run_id, token_id=token_id, pair_id=pair_id,
            token_mint=MINT, pair_address=PAIR, tracking_lane="TRACK_FAST",
            explicit_proof_mode=True,
        )
        self.assertFalse(consumed["planned"])
        self.assertIn("already_consumed", " ".join(consumed["blocked_reasons"]))

    def test_clean_close_runs_e2q_lane_q_lane_k_and_is_idempotent(self) -> None:
        run_id, token_id, pair_id, _, _ = self._foundation()
        policy = get_policy("WINDOW_4H", "TRACK_FAST")
        assert policy is not None
        first_id = None
        closing_id = None
        for index in range(policy.minimum_required_snapshots):
            snapshot_id = self._snapshot(
                token_id, pair_id, "TRACK_FAST",
                T0 + timedelta(seconds=index * policy.target_snapshot_interval_seconds),
            )
            if index == 0:
                first_id = snapshot_id
            if index == policy.minimum_required_snapshots - 1:
                closing_id = snapshot_id
                step_kind = "LONG_CONTINUATION_CLOSE"
                step_status = "RUNNING"
                step_key = "t1_p1_4h_close"
            else:
                step_kind = "LONG_CONTINUATION_SNAPSHOT"
                step_status = "SUCCEEDED"
                step_key = f"t1_p1_4h_snapshot_{index:03d}"
            self.conn.execute(
                """INSERT INTO printer_memory_factory_run_steps
                   (run_id,step_key,step_kind,step_status,token_id,pair_id,
                    token_mint,pair_address,tracking_lane,snapshot_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (run_id, step_key, step_kind, step_status, token_id, pair_id,
                 MINT, PAIR, "TRACK_FAST", snapshot_id),
            )
        assert first_id is not None and closing_id is not None
        close_step = {
            "run_id": run_id, "token_id": token_id, "pair_id": pair_id,
            "token_mint": MINT, "pair_address": PAIR, "tracking_lane": "TRACK_FAST",
        }
        self.conn.commit()
        result = close_current_run_4h(
            self.conn, run_id=run_id, close_step=close_step,
            closing_snapshot_id=closing_id,
            execution_authority=FourHourExecutionAuthority.PROOF,
        )
        self.conn.commit()
        self.assertTrue(result["closed"])
        self.assertFalse(result["dirty"])
        self.assertEqual(result["cadence"]["actual_snapshot_count"], 61)
        missing_context = run_4h_quality_gates(str(self.db), int(result["window_id"]))
        self.assertEqual(missing_context["lane_k_status"], "LANE_K_BLOCKED")
        window = self.conn.execute(
            "SELECT supporting_context_json FROM printer_memory_windows WHERE id=?",
            (result["window_id"],),
        ).fetchone()
        context = json.loads(window["supporting_context_json"])
        context["shared_window_4h_context_evidence"] = {
            "clean_memory_context_ready": True
        }
        self.conn.execute(
            "UPDATE printer_memory_windows SET supporting_context_json=? WHERE id=?",
            (json.dumps(context, sort_keys=True), result["window_id"]),
        )
        self.conn.commit()
        outcome_owner = getattr(factory, "_derive_and_persist_four_hour_outcome", None)
        self.assertIsNotNone(
            outcome_owner,
            "canonical full-path WINDOW_4H outcome owner is missing",
        )
        outcome = outcome_owner(
            self.conn,
            run_id=run_id,
            token_id=token_id,
            pair_id=pair_id,
            window_id=int(result["window_id"]),
            current_close_snapshot_id=int(closing_id),
        )
        self.conn.commit()
        self.assertNotEqual(outcome["outcome_label"], "OUTCOME_UNKNOWN")
        quality = run_4h_quality_gates(str(self.db), int(result["window_id"]))
        self.assertEqual(quality["lane_k_status"], "LANE_K_COMPLETED")
        self.assertEqual(quality["lane_q"]["valid_window_ids"], [result["window_id"]])
        replay = run_4h_quality_gates(str(self.db), int(result["window_id"]))
        self.assertEqual(replay["memory"]["e2z_status"], "E2Z_ALREADY_EXISTS")
        for table in (
            "printer_memory_retrieval_queries", "printer_memory_retrieval_matches",
            "printer_paper_decisions", "printer_paper_positions",
            "printer_paper_trade_events", "printer_paper_trade_audits",
        ):
            self.assertEqual(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)

    def test_historical_snapshot_between_ids_is_not_cadence_evidence(self) -> None:
        run_id, token_id, pair_id, _, _ = self._foundation()
        policy = get_policy("WINDOW_4H", "TRACK_FAST")
        assert policy is not None
        closing_id = None
        for index in range(policy.minimum_required_snapshots):
            snapshot_id = self._snapshot(
                token_id, pair_id, "TRACK_FAST",
                T0 + timedelta(seconds=index * policy.target_snapshot_interval_seconds),
            )
            if index == 10:
                self._snapshot(
                    token_id, pair_id, "TRACK_FAST",
                    T0 + timedelta(seconds=index * policy.target_snapshot_interval_seconds + 1),
                )
            is_close = index == policy.minimum_required_snapshots - 1
            closing_id = snapshot_id if is_close else closing_id
            self.conn.execute(
                """INSERT INTO printer_memory_factory_run_steps
                   (run_id,step_key,step_kind,step_status,token_id,pair_id,
                    token_mint,pair_address,tracking_lane,snapshot_id)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (
                    run_id,
                    "t1_p1_4h_close" if is_close else f"t1_p1_4h_snapshot_{index:03d}",
                    "LONG_CONTINUATION_CLOSE" if is_close else "LONG_CONTINUATION_SNAPSHOT",
                    "RUNNING" if is_close else "SUCCEEDED",
                    token_id, pair_id, MINT, PAIR, "TRACK_FAST", snapshot_id,
                ),
            )
        self.conn.commit()
        result = close_current_run_4h(
            self.conn,
            run_id=run_id,
            close_step={
                "token_id": token_id,
                "pair_id": pair_id,
                "tracking_lane": "TRACK_FAST",
            },
            closing_snapshot_id=int(closing_id),
            execution_authority=FourHourExecutionAuthority.PROOF,
        )
        self.assertTrue(result["closed"])
        self.assertEqual(result["cadence"]["actual_snapshot_count"], 61)


if __name__ == "__main__":
    unittest.main()
