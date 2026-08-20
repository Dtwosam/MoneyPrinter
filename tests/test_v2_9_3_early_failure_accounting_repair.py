"""V2-9.3 early-failure propagation and unreached-phase accounting tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
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
    TOKEN_LOCAL_CANCELLED,
    _GlobalStop,
    _apply_post_report_integrity,
    _cancel_pending_for_token,
    _counts,
    _enforce_budgets_before_step,
    _final_report,
    _four_hour_terminal_validation,
    load_report_only,
)


T0 = datetime(2026, 7, 15, 15, 50, tzinfo=timezone.utc)
MINT = "E" * 32
PAIR = "F" * 32
TLS_TYPE = "dexscreener_transport_failure"
TLS_MESSAGE = "<urlopen error _ssl.c:993: The handshake operation timed out>"


class EarlyFailureAccountingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(dir=Path.cwd())
        self.db = Path(self.temp.name) / "fixture.sqlite3"
        apply_migrations(self.db)
        self.conn = sqlite3.connect(self.db)
        self.conn.row_factory = sqlite3.Row
        self.run_id = "run-v2-9-3"
        config = {"continuous_first_hour": True, "continuous_four_hour": True}
        self.conn.execute(
            """INSERT INTO printer_memory_factory_runs
               (run_id,run_status,window_kind,db_mode,config_hash,config_json,
                selected_token_count,started_at)
               VALUES (?,'RUNNING','WINDOW_15M','PROOF_ONLY','hash',?,1,?)""",
            (self.run_id, json.dumps(config), T0.isoformat()),
        )
        self.token_id = int(self.conn.execute(
            "INSERT INTO printer_tokens(token_mint,chain,token_status) VALUES (?,'solana','TRACK_FAST')",
            (MINT,),
        ).lastrowid)
        self.pair_id = int(self.conn.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (self.token_id, PAIR, MINT),
        ).lastrowid)
        self.conn.commit()
        self.before = _counts(self.conn)

    def tearDown(self) -> None:
        self.conn.close()
        self.temp.cleanup()

    def _request(self, key: str) -> int:
        return int(self.conn.execute(
            """INSERT INTO printer_source_requests
               (source_name,request_kind,requested_at,request_key,source_status,data_quality_label)
               VALUES ('dexscreener','pair_market_snapshot',?,?,'COMPLETE','CLEAN_DATA')""",
            (T0.isoformat(), key),
        ).lastrowid)

    def _source_failure_report(self, step_kind: str) -> dict[str, object]:
        request_id = self._request(f"{self.run_id}:failed")
        failure_id = int(self.conn.execute(
            """INSERT INTO printer_source_failures
               (source_name,request_kind,failed_at,failure_type,failure_message,
                source_status,data_quality_label)
               VALUES ('dexscreener','pair_market_snapshot',?,?,?,'FAILED','MISSING_CRITICAL_DATA')""",
            (T0.isoformat(), TLS_TYPE, TLS_MESSAGE),
        ).lastrowid)
        failed_job_id = int(self.conn.execute(
            """INSERT INTO printer_scheduler_jobs
               (job_name,job_kind,status,scheduled_for,finished_at,retry_count,last_error)
               VALUES ('failed','TOKEN_SNAPSHOT','FAILED',?,?,1,?)""",
            (T0.isoformat(), T0.isoformat(), TLS_TYPE),
        ).lastrowid)
        self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,scheduled_for,scheduler_job_id,
                source_request_id,source_failure_id,result_json,error_or_skip_reason,finished_at)
               VALUES (?,'failed_step',?,'FAILED',?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                self.run_id, step_kind, self.token_id, self.pair_id, MINT, PAIR,
                "TRACK_FAST", T0.isoformat(), failed_job_id, request_id, failure_id,
                json.dumps({"blocked_reason": TLS_TYPE}), TLS_TYPE, T0.isoformat(),
            ),
        )
        pending_job_id = int(self.conn.execute(
            """INSERT INTO printer_scheduler_jobs
               (job_name,job_kind,status,scheduled_for)
               VALUES ('pending','TOKEN_SNAPSHOT','PENDING',?)""",
            ((T0 + timedelta(minutes=1)).isoformat(),),
        ).lastrowid)
        self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane,scheduled_for,scheduler_job_id)
               VALUES (?,'pending_step',?,'PENDING',?,?,?,?,?,?,?)""",
            (
                self.run_id, step_kind, self.token_id, self.pair_id, MINT, PAIR,
                "TRACK_FAST", (T0 + timedelta(minutes=1)).isoformat(), pending_job_id,
            ),
        )
        self.conn.commit()
        self.assertEqual(
            _cancel_pending_for_token(
                self.conn, self.run_id, self.token_id, TOKEN_LOCAL_CANCELLED,
            ),
            1,
        )
        self.conn.commit()
        report = _final_report(
            self.conn,
            run_id=self.run_id,
            config={"continuous_first_hour": True, "continuous_four_hour": True},
            discovery={"source_budget_report": {"source_requests_attempted": 2}},
            before=self.before,
            stop_reason=STOP_COMPLETED,
            started_at=T0.isoformat(),
        )
        self.conn.execute(
            """UPDATE printer_memory_factory_runs
               SET run_status=?,stop_reason=?,finished_at=?,final_report_json=?
               WHERE run_id=?""",
            (
                report["run_status"], report["stop_reason"], report["finished_at"],
                json.dumps(report, sort_keys=True), self.run_id,
            ),
        )
        self.conn.commit()
        return report

    def _assert_early_source_failure(self, report: dict[str, object], stage: str) -> None:
        self.assertEqual(report["run_status"], "FAILED")
        self.assertEqual(report["stop_reason"], STOP_SOURCE)
        cause = report["primary_terminal_cause"]
        self.assertEqual(cause["category"], "SOURCE_FAILURE")
        self.assertEqual(cause["stage"], stage)
        self.assertTrue(cause["pre_four_hour"])
        self.assertEqual(cause["failure_type"], TLS_TYPE)
        self.assertEqual(cause["failure_message"], TLS_MESSAGE)
        phase = report["four_hour_phase_usage"]
        self.assertEqual(phase["state"], "NOT_STARTED")
        self.assertEqual(phase["source_requests"], 0)
        self.assertEqual(phase["scheduler_rows"], 0)
        self.assertIsNone(phase["budget_verdict"])
        self.assertIsNone(phase["within_ceiling"])
        cumulative = report["cumulative_lifecycle_usage"]
        self.assertEqual(cumulative["state"], "REPORTED")
        self.assertEqual(cumulative["budget_verdict"], "WITHIN_CEILING")
        self.assertTrue(cumulative["within_ceiling"])
        terminal = report["four_hour_terminal_validation"]
        self.assertEqual(terminal["phase_state"], "NOT_STARTED")
        self.assertEqual(terminal["stop_reason"], STOP_SOURCE)
        self.assertNotIn("four_hour_phase_budget_exceeded", terminal["reasons"])
        self.assertNotIn("cumulative_lifecycle_budget_exceeded", terminal["reasons"])
        self.assertEqual(terminal["budget_failure_scopes"], [])
        self.assertTrue(terminal["cleanup_complete"])
        self.assertEqual(report["running_jobs_after_stop"], 0)
        self.assertEqual(report["pending_or_running_run_steps"], 0)
        self.assertEqual(report["table_deltas"]["printer_memory_windows"], 0)
        self.assertEqual(report["table_deltas"]["printer_memories"], 0)
        self.assertEqual(report["table_deltas"]["printer_memory_fingerprints"], 0)
        self.assertFalse(any(report["forbidden_deltas"].values()))

    def test_15m_tls_failure_is_primary_and_replay_is_zero_delta(self) -> None:
        report = self._source_failure_report("SNAPSHOT")
        self._assert_early_source_failure(report, "PRE_4H_15M")
        before_hash = hashlib.sha256(self.db.read_bytes()).hexdigest()
        replay = load_report_only(self.db, self.run_id)
        after_hash = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.assertEqual(before_hash, after_hash)
        self.assertEqual(
            replay["replay"],
            {"mode": "REPORT_ONLY", "new_source_calls": 0, "new_evidence_rows": 0},
        )

    def test_1h_tls_failure_is_primary_and_pre_four_hour(self) -> None:
        report = self._source_failure_report("CONTINUATION_SNAPSHOT")
        self._assert_early_source_failure(report, "PRE_4H_1H")

    def test_projected_phase_budget_breach_has_phase_scope(self) -> None:
        for index in range(69):
            self._request(f"{self.run_id}:t1_p1_4h_{index:03d}")
        step = self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane)
               VALUES (?,'t1_p1_4h_next','LONG_CONTINUATION_SNAPSHOT','PENDING',?,?,?,?,?)
               RETURNING *""",
            (self.run_id, self.token_id, self.pair_id, MINT, PAIR, "TRACK_FAST"),
        ).fetchone()
        with self.assertRaises(_GlobalStop) as raised:
            _enforce_budgets_before_step(self.conn, self.run_id, step)
        self.assertEqual(raised.exception.reason, STOP_BUDGET)
        self.assertEqual(raised.exception.scope, "FOUR_HOUR_PHASE")

    def test_projected_cumulative_budget_breach_has_distinct_scope(self) -> None:
        self._request(f"{self.run_id}:t1_p1_4h_000")
        # V2-9.8B first-hour safety provenance repair: the cumulative TRACK_FAST
        # request ceiling includes 4 reserved fresh 1h safety requests, so
        # the projected breach needs one additional prior request.
        for index in range(117):
            self._request(f"{self.run_id}:earlier_{index:03d}")
        step = self.conn.execute(
            """INSERT INTO printer_memory_factory_run_steps
               (run_id,step_key,step_kind,step_status,token_id,pair_id,token_mint,
                pair_address,tracking_lane)
               VALUES (?,'t1_p1_4h_next','LONG_CONTINUATION_SNAPSHOT','PENDING',?,?,?,?,?)
               RETURNING *""",
            (self.run_id, self.token_id, self.pair_id, MINT, PAIR, "TRACK_FAST"),
        ).fetchone()
        with self.assertRaises(_GlobalStop) as raised:
            _enforce_budgets_before_step(self.conn, self.run_id, step)
        self.assertEqual(raised.exception.reason, STOP_BUDGET)
        self.assertEqual(raised.exception.scope, "CUMULATIVE_LIFECYCLE")

    def test_actual_budget_scopes_are_distinct_and_source_precedence_wins(self) -> None:
        steps = [{
            "id": 1, "step_key": "4h", "step_kind": "LONG_CONTINUATION_SNAPSHOT",
            "step_status": "FAILED", "tracking_lane": "TRACK_FAST",
            "snapshot_id": None, "source_failure_id": None,
            "error_or_skip_reason": STOP_BUDGET,
        }]
        phase_breach = _four_hour_terminal_validation(
            config={"continuous_four_hour": True}, steps=steps, windows_by_id={},
            budgets={
                "four_hour_phase_usage": {
                    "state": "STARTED", "tracking_lane": "TRACK_FAST",
                    "budget_verdict": "EXCEEDED",
                },
                "cumulative_lifecycle_usage": {"budget_verdict": "WITHIN_CEILING"},
            },
            pending_steps=0, running_jobs=0,
        )
        self.assertEqual(phase_breach["stop_reason"], STOP_BUDGET)
        self.assertEqual(phase_breach["budget_failure_scopes"], ["FOUR_HOUR_PHASE"])

        cumulative_breach = _four_hour_terminal_validation(
            config={"continuous_four_hour": True}, steps=steps, windows_by_id={},
            budgets={
                "four_hour_phase_usage": {
                    "state": "STARTED", "tracking_lane": "TRACK_FAST",
                    "budget_verdict": "WITHIN_CEILING",
                },
                "cumulative_lifecycle_usage": {"budget_verdict": "EXCEEDED"},
            },
            pending_steps=0, running_jobs=0,
        )
        self.assertEqual(cumulative_breach["stop_reason"], STOP_BUDGET)
        self.assertEqual(
            cumulative_breach["budget_failure_scopes"], ["CUMULATIVE_LIFECYCLE"],
        )

        source_primary = {
            "present": True, "category": "SOURCE_FAILURE", "run_status": "FAILED",
            "stop_reason": STOP_SOURCE, "stage": "PRE_4H_15M",
            "failure_type": TLS_TYPE, "failure_message": TLS_MESSAGE,
        }
        precedence = _four_hour_terminal_validation(
            config={"continuous_four_hour": True}, steps=[], windows_by_id={},
            budgets={
                "four_hour_phase_usage": {
                    "state": "NOT_STARTED", "tracking_lane": "TRACK_FAST",
                    "budget_verdict": None,
                },
                "cumulative_lifecycle_usage": {"budget_verdict": "EXCEEDED"},
            },
            pending_steps=0, running_jobs=0, primary_cause=source_primary,
        )
        self.assertEqual(precedence["run_status"], "FAILED")
        self.assertEqual(precedence["stop_reason"], STOP_SOURCE)
        self.assertEqual(precedence["primary_cause"]["failure_message"], TLS_MESSAGE)


    def test_cleanup_details_do_not_replace_primary_cause(self) -> None:
        failed = {
            "run_status": "FAILED",
            "stop_reason": STOP_SOURCE,
            "running_jobs_after_stop": 1,
            "forbidden_deltas": {"printer_paper_decisions": 1},
            "secondary_terminal_details": [],
        }
        _apply_post_report_integrity(failed)
        self.assertEqual(failed["run_status"], "FAILED")
        self.assertEqual(failed["stop_reason"], STOP_SOURCE)
        self.assertEqual(len(failed["secondary_terminal_details"]), 2)

        otherwise_complete = {
            "run_status": "COMPLETED",
            "stop_reason": STOP_COMPLETED,
            "running_jobs_after_stop": 1,
            "forbidden_deltas": {},
            "secondary_terminal_details": [],
        }
        _apply_post_report_integrity(otherwise_complete)
        self.assertEqual(otherwise_complete["run_status"], "SAFE_STOPPED")
        self.assertNotEqual(otherwise_complete["stop_reason"], STOP_COMPLETED)

if __name__ == "__main__":
    unittest.main()
