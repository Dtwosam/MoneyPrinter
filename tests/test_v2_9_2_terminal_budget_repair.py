"""V2-9.2 deterministic terminal-state and budget-accounting repair tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.one_command_15m_factory import (
    STOP_BUDGET,
    STOP_COMPLETED,
    STOP_SOURCE,
    STOP_TERMINAL_4H,
    _GlobalStop,
    _counts,
    _enforce_budgets_before_step,
    _final_report,
    _four_hour_terminal_validation,
    _run_budgets,
)
from printer_v1.operator_cli.one_token_4h_runtime import (
    cumulative_lifecycle_budget,
    plan_current_run_4h,
    require_projected_capacity,
    runtime_budget,
)


T0 = datetime(2026, 7, 15, 12, 0, tzinfo=timezone.utc)
MINT = "C" * 32
PAIR = "D" * 32


def _good_budgets() -> dict[str, object]:
    return {
        "four_hour_phase_usage": {"within_ceiling": True},
        "cumulative_lifecycle_usage": {"within_ceiling": True},
    }


def _long_steps(
    *, count: int, lane: str = "TRACK_NORMAL", close_status: str = "CANCELLED",
    window_id: int | None = None, close_result: dict[str, object] | None = None,
    error: str | None = None, source_failure_id: int | None = None,
) -> list[dict[str, object]]:
    steps: list[dict[str, object]] = []
    for index in range(count):
        is_close = index == count - 1
        steps.append({
            "step_kind": "LONG_CONTINUATION_CLOSE" if is_close else "LONG_CONTINUATION_SNAPSHOT",
            "step_status": close_status if is_close else "SUCCEEDED",
            "tracking_lane": lane,
            "snapshot_id": index + 1,
            "memory_window_id": window_id if is_close else None,
            "result_json": json.dumps(close_result or {}) if is_close else None,
            "error_or_skip_reason": error if is_close else None,
            "source_failure_id": source_failure_id if is_close else None,
        })
    return steps


class TerminalSemanticsTests(unittest.TestCase):
    def test_incomplete_24_of_31_without_forced_close_or_successor_never_completes(self) -> None:
        result = _four_hour_terminal_validation(
            config={"continuous_four_hour": True},
            steps=_long_steps(count=24), windows_by_id={}, budgets=_good_budgets(),
            pending_steps=0, running_jobs=0,
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["run_status"], "SAFE_STOPPED")
        self.assertEqual(result["stop_reason"], STOP_TERMINAL_4H)
        self.assertIn("incomplete_4h_collection:24/31", result["reasons"])
        self.assertIn("forced_close_not_succeeded:CANCELLED", result["reasons"])
        self.assertIn("missing_window_4h_successor", result["reasons"])
        self.assertIsNone(result["successor_window_id"])

    def test_terminal_transport_failure_preserves_reason_and_fails_honestly(self) -> None:
        exact = "DexScreener transport failure: connection reset"
        result = _four_hour_terminal_validation(
            config={"continuous_four_hour": True},
            steps=_long_steps(
                count=24, close_status="FAILED", error=exact, source_failure_id=77,
            ),
            windows_by_id={}, budgets=_good_budgets(), pending_steps=0, running_jobs=0,
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["run_status"], "FAILED")
        self.assertEqual(result["stop_reason"], STOP_SOURCE)
        self.assertEqual(result["source_failure_reasons"], [exact])
        self.assertTrue(result["cleanup_complete"])

    def test_completed_requires_exact_collection_successor_and_audit_path(self) -> None:
        audit = {
            "window_audit": {}, "lane_q": {},
            "memory_pipeline": {"lane_k_status": "LANE_K_BLOCKED"},
        }
        result = _four_hour_terminal_validation(
            config={"continuous_four_hour": True},
            steps=_long_steps(
                count=31, close_status="SUCCEEDED", window_id=41, close_result=audit,
            ),
            windows_by_id={41: {"id": 41, "window_kind": "WINDOW_4H"}},
            budgets=_good_budgets(), pending_steps=0, running_jobs=0,
        )
        self.assertTrue(result["complete"])
        self.assertEqual(result["run_status"], "COMPLETED")
        self.assertEqual(result["stop_reason"], STOP_COMPLETED)
        self.assertTrue(result["audit_path_complete"])

        missing_audit = _four_hour_terminal_validation(
            config={"continuous_four_hour": True},
            steps=_long_steps(count=31, close_status="SUCCEEDED", window_id=41),
            windows_by_id={41: {"id": 41, "window_kind": "WINDOW_4H"}},
            budgets=_good_budgets(), pending_steps=0, running_jobs=0,
        )
        self.assertFalse(missing_audit["complete"])
        self.assertIn("incomplete_4h_audit_report_path", missing_audit["reasons"])

    def test_budget_or_cleanup_failure_never_completes(self) -> None:
        audit = {
            "window_audit": {}, "lane_q": {},
            "memory_pipeline": {"lane_k_status": "LANE_K_BLOCKED"},
        }
        budgets = _good_budgets()
        budgets["four_hour_phase_usage"] = {"within_ceiling": False}
        result = _four_hour_terminal_validation(
            config={"continuous_four_hour": True},
            steps=_long_steps(
                count=31, close_status="SUCCEEDED", window_id=41, close_result=audit,
            ),
            windows_by_id={41: {"id": 41, "window_kind": "WINDOW_4H"}},
            budgets=budgets, pending_steps=1, running_jobs=1,
        )
        self.assertFalse(result["complete"])
        self.assertEqual(result["stop_reason"], STOP_BUDGET)
        self.assertFalse(result["cleanup_complete"])


class BudgetAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        # Keep fixture DBs inside the writable repository sandbox on Windows.
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.db = Path(self.temp.name) / "fixture.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _run(self, lane: str = "TRACK_NORMAL") -> str:
        run_id = f"run-{lane.lower()}"
        config = {"continuous_first_hour": True, "continuous_four_hour": True}
        self.conn.execute(
            """INSERT INTO printer_memory_factory_runs
               (run_id,run_status,window_kind,db_mode,config_hash,config_json,
                selected_token_count,started_at)
               VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','hash',?,1,?)""",
            (run_id, json.dumps(config), T0.isoformat()),
        )
        return run_id

    def _request(self, key: str) -> None:
        self.conn.execute(
            """INSERT INTO printer_source_requests
               (source_name,request_kind,requested_at,request_key,source_status,data_quality_label)
               VALUES ('dexscreener','TOKEN_SNAPSHOT',?,?,'COMPLETE','CLEAN_DATA')""",
            (T0.isoformat(), key),
        )

    def _step(self, run_id: str, lane: str, key: str, kind: str) -> sqlite3.Row:
        self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane)
               VALUES (?,?,?,'PENDING',1,1,?,?,?)""",
            (run_id, key, kind, MINT, PAIR, lane),
        )
        self.conn.commit()
        return self.conn.execute(
            "SELECT * FROM printer_memory_factory_run_steps WHERE run_id=? AND step_key=?",
            (run_id, key),
        ).fetchone()

    def test_phase_and_policy_derived_cumulative_ceilings_are_exact(self) -> None:
        # V2-9.8B first-hour safety provenance repair: the cumulative request
        # ceiling gained the 3 fresh governed safety transports reserved by the
        # exact 1h close. Phase and Scheduler ceilings are unchanged.
        expected = {
            "TRACK_FAST": (69, 64, 119, 105),
            "TRACK_NORMAL": (39, 34, 71, 57),
        }
        for lane, values in expected.items():
            with self.subTest(lane=lane):
                phase = runtime_budget(lane)
                cumulative = cumulative_lifecycle_budget(lane)
                self.assertEqual(
                    (phase["phase_request_ceiling"], phase["phase_scheduler_ceiling"],
                     cumulative["request_ceiling"], cumulative["scheduler_ceiling"]),
                    values,
                )
                self.assertEqual(
                    cumulative["request_ceiling"],
                    sum(cumulative["request_components"].values()),
                )
                self.assertEqual(
                    cumulative["scheduler_ceiling"],
                    sum(cumulative["scheduler_components"].values()),
                )

    def test_exact_request_ceiling_passes_and_one_above_stops_before_creation(self) -> None:
        run_id = self._run()
        for index in range(38):
            self._request(f"{run_id}:t1_p1_4h_snapshot_{index:03d}")
        step = self._step(
            run_id, "TRACK_NORMAL", "t1_p1_4h_snapshot_038", "LONG_CONTINUATION_SNAPSHOT",
        )
        _enforce_budgets_before_step(self.conn, run_id, step)
        self._request(f"{run_id}:t1_p1_4h_snapshot_038")
        self.conn.commit()
        before = self.conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0]
        with self.assertRaises(_GlobalStop) as raised:
            _enforce_budgets_before_step(self.conn, run_id, step)
        self.assertEqual(raised.exception.reason, STOP_BUDGET)
        after = self.conn.execute(
            "SELECT COUNT(*) FROM printer_source_requests"
        ).fetchone()[0]
        self.assertEqual(after, before)

    def test_scheduler_overage_stops_before_any_4h_job_or_step_is_created(self) -> None:
        run_id = self._run()
        token_id = int(self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_NORMAL')",
            (MINT,),
        ).lastrowid)
        pair_id = int(self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (token_id, PAIR, MINT),
        ).lastrowid)
        snapshot_id = int(self.conn.execute(
            """INSERT INTO printer_token_snapshots
               (token_id,pair_id,captured_at,tracking_lane,snapshot_mode,source_status,data_quality_label)
               VALUES (?,?,?,'TRACK_NORMAL','TOKEN_SNAPSHOT','COMPLETE','CLEAN_DATA')""",
            (token_id, pair_id, T0.isoformat()),
        ).lastrowid)
        predecessor_id = int(self.conn.execute(
            """INSERT INTO printer_memory_windows
               (token_id,pair_id,window_kind,opened_at,closed_at,memory_status,window_status,
                data_quality_label,do_not_train,supporting_context_json,window_start_at,
                window_end_at,snapshot_start_id,snapshot_end_id)
               VALUES (?,?,'WINDOW_1H',?,?,'PARTIAL_MEMORY','WINDOW_CLOSED','CLEAN_DATA',0,'{}',?,?,?,?)""",
            (token_id, pair_id, (T0-timedelta(hours=1)).isoformat(), T0.isoformat(),
             (T0-timedelta(hours=1)).isoformat(), T0.isoformat(), snapshot_id, snapshot_id),
        ).lastrowid)
        self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,snapshot_id,memory_window_id)
               VALUES (?,'close_1h','CONTINUATION_CLOSE','SUCCEEDED',?,?,?,?,?,?,?)""",
            (run_id, token_id, pair_id, MINT, PAIR, "TRACK_NORMAL", snapshot_id, predecessor_id),
        )
        for index in range(26):
            job_id = int(self.conn.execute(
                """INSERT INTO printer_scheduler_jobs
                   (job_name,job_kind,status,scheduled_for)
                   VALUES (?, 'TOKEN_SNAPSHOT', 'COMPLETED', ?)""",
                (f"earlier-{index}", T0.isoformat()),
            ).lastrowid)
            self.conn.execute(
                """INSERT INTO printer_memory_factory_run_steps
                   (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                    pair_address,tracking_lane,scheduler_job_id)
                   VALUES (?,?, 'SNAPSHOT', 'SUCCEEDED',?,?,?,?,?,?)""",
                (run_id, f"earlier-{index}", token_id, pair_id, MINT, PAIR,
                 "TRACK_NORMAL", job_id),
            )
        self.conn.commit()
        jobs_before = self.conn.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0]
        steps_before = self.conn.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_run_steps"
        ).fetchone()[0]
        with self.assertRaises(ValueError):
            plan_current_run_4h(
                self.conn, run_id=run_id, token_id=token_id, pair_id=pair_id,
                token_mint=MINT, pair_address=PAIR, tracking_lane="TRACK_NORMAL",
                explicit_proof_mode=True,
            )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM printer_scheduler_jobs").fetchone()[0],
            jobs_before,
        )
        self.assertEqual(
            self.conn.execute("SELECT COUNT(*) FROM printer_memory_factory_run_steps").fetchone()[0],
            steps_before,
        )

    def test_report_separates_phase_from_cumulative_usage(self) -> None:
        run_id = self._run()
        for index in range(5):
            self._request(f"{run_id}:t1_p1_4h_snapshot_{index:03d}")
        for index in range(10):
            self._request(f"{run_id}:t1_p1_earlier_{index:03d}")
        step = self._step(
            run_id, "TRACK_NORMAL", "t1_p1_4h_snapshot_000", "LONG_CONTINUATION_SNAPSHOT",
        )
        report = _run_budgets(
            self.conn, run_id,
            {"source_budget_report": {"source_requests_attempted": 2}},
            [dict(step)],
        )
        self.assertEqual(report["four_hour_phase_usage"]["source_requests"], 5)
        self.assertEqual(report["four_hour_phase_usage"]["source_request_ceiling"], 39)
        self.assertEqual(report["cumulative_lifecycle_usage"]["source_requests"], 17)
        self.assertEqual(report["cumulative_lifecycle_usage"]["source_request_ceiling"], 71)
        self.assertTrue(report["cumulative_lifecycle_usage"]["policy_derived"])

    def test_final_report_overrides_stale_completed_reason_after_transport_failure(self) -> None:
        run_id = self._run()
        token_id = int(self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_NORMAL')",
            (MINT,),
        ).lastrowid)
        pair_id = int(self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (token_id, PAIR, MINT),
        ).lastrowid)
        before = _counts(self.conn)
        exact = "DexScreener transport failure: connection reset"
        self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,error_or_skip_reason)
               VALUES (?,'t1_p1_4h_snapshot_024','LONG_CONTINUATION_SNAPSHOT','FAILED',
                       ?,?,?,?,?,?)""",
            (run_id, token_id, pair_id, MINT, PAIR, "TRACK_NORMAL", exact),
        )
        self.conn.commit()
        report = _final_report(
            self.conn, run_id=run_id,
            config={"continuous_first_hour": True, "continuous_four_hour": True},
            discovery={"source_budget_report": {"source_requests_attempted": 0}},
            before=before, stop_reason=STOP_COMPLETED, started_at=T0.isoformat(),
        )
        self.assertEqual(report["run_status"], "FAILED")
        self.assertEqual(report["stop_reason"], STOP_SOURCE)
        self.assertEqual(
            report["four_hour_terminal_validation"]["source_failure_reasons"],
            [exact],
        )
        self.assertEqual(report["running_jobs_after_stop"], 0)
    def test_capacity_helper_accepts_exact_and_rejects_one_over(self) -> None:
        require_projected_capacity(current=33, projected=1, ceiling=34, label="scheduler")
        with self.assertRaises(ValueError):
            require_projected_capacity(current=34, projected=1, ceiling=34, label="scheduler")


if __name__ == "__main__":
    unittest.main()
