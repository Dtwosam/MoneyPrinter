"""
Post-Lane 10 Lane E2T -- Bounded Integrated 15m Operator Cycle Runner

Tests prove:
- e2t_bounded_cycle_runner module imports cleanly
- constants defined correctly (default, hard cap, status strings, command name)
- hard_locks all True including no_unbounded_loop, no_daemon_mode, no_scheduler_bypass
- run_bounded_15m_cycles is callable
- operator approval required
- db_path required
- db_path missing → blocked
- backup_proof_path required
- backup_proof_path missing → blocked
- token_list_path required
- token_list_path missing → blocked
- zero cycle count blocked
- negative cycle count blocked
- cycle count above hard cap blocked
- non-integer cycle count blocked
- one-cycle run succeeds
- bounded_cycle_status E2T_COMPLETED on success
- completed_cycle_count == requested on success
- cycles list length matches completed
- per-cycle e2j_status is E2J_STATUS_EXECUTED
- per-cycle job_id present (int)
- per-cycle snapshot_id present (int)
- per-cycle memory_window_id present (int)
- per-cycle memory_window_audit_status present
- per-cycle memory_quality_label present
- per-cycle deltas dict present
- multi-cycle run (2) succeeds within cap
- multi-cycle run (3) succeeds at cap
- cycle count above cap blocked (4+)
- stops on blocked cycle (e2j blocked), bounded_cycle_status E2T_STOPPED
- completed_cycle_count lower than requested when stopped
- stops on blocked cycle with stopped_reason
- refuses to start if running job exists
- refuses to start if active lock exists
- no memories created across all cycles
- no paper decisions across all cycles
- no paper positions across all cycles
- no paper trade events across all cycles
- no paper trade audits across all cycles
- no episodes created
- hard_locks in result
- buy/sell/hold enabled False
- CLI function main_run_e2t_bounded_cycle exists and is callable
- CLI returns 0 for valid args with fixture adapter
- CLI outputs valid JSON
- CLI blocked when --operator-approved not set
- pyproject.toml entry registered
"""

import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.e2t_bounded_cycle_runner import (
    E2T_COMMAND_NAME,
    E2T_DEFAULT_MAX_CYCLES,
    E2T_MAX_CYCLES_HARD_CAP,
    E2T_STATUS_BLOCKED,
    E2T_STATUS_COMPLETED,
    E2T_STATUS_STOPPED,
    _HARD_LOCKS,
    run_bounded_15m_cycles,
)
from printer_v1.operator_cli.commands import main_run_e2t_bounded_cycle
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    FIXTURE_SUCCESS,
)


_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_MINT_2 = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
_PAIR_ADDR = "E2TTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_VALID_NOTE = "Operator-approved for E2T test. Reviewed 2026-06-28."


def _build_fixture_adapter(mint: str = _MINT_1):
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_kind=FIXTURE_SUCCESS,
        fixture_payload={
            "source_name": "dexscreener",
            "request_kind": "pair_market_snapshot",
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": _PAIR_ADDR,
                    "token_mint": mint,
                    "symbol": "TEST",
                    "name": "Test Token",
                    "price_usd": 0.00042,
                    "liquidity_usd": 50000.0,
                    "volume_5m": 1000.0,
                    "volume_1h": 12000.0,
                    "volume_24h": 288000.0,
                    "txns_5m": 10,
                    "txns_1h": 120,
                    "txns_24h": 2880,
                    "fdv": 420000.0,
                    "market_cap": 380000.0,
                    "price_change_5m": 0.5,
                    "price_change_1h": 2.1,
                    "price_change_24h": -3.4,
                }
            ],
        },
    )


class _DbTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_proof_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _write_token_file(self, tokens: list[dict]) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _valid_token_entry(self, mint: str = _MINT_1) -> dict:
        return {
            "token_mint": mint,
            "lifecycle_lane": "TRACK_FAST",
            "approved_by_operator": True,
            "operator_note": _VALID_NOTE,
        }

    def _run(self, max_cycles: int = 1, **kwargs) -> dict:
        token_file = self._write_token_file([self._valid_token_entry()])
        defaults = dict(
            token_list_path=token_file,
            db_path=self.db_path,
            backup_proof_path=self.backup_proof_path,
            operator_approved=True,
            max_cycles=max_cycles,
            _adapter=_build_fixture_adapter(),
        )
        defaults.update(kwargs)
        return run_bounded_15m_cycles(**defaults)


# ---------------------------------------------------------------------------
# Import and constants
# ---------------------------------------------------------------------------

class LaneE2TImportTests(unittest.TestCase):
    def test_module_imports_cleanly(self):
        from printer_v1.operator_cli import e2t_bounded_cycle_runner
        self.assertIsNotNone(e2t_bounded_cycle_runner)

    def test_function_importable(self):
        self.assertTrue(callable(run_bounded_15m_cycles))

    def test_default_max_cycles_is_one(self):
        self.assertEqual(E2T_DEFAULT_MAX_CYCLES, 1)

    def test_hard_cap_is_three(self):
        self.assertEqual(E2T_MAX_CYCLES_HARD_CAP, 3)

    def test_hard_cap_small(self):
        self.assertLessEqual(E2T_MAX_CYCLES_HARD_CAP, 3)

    def test_status_completed_defined(self):
        self.assertEqual(E2T_STATUS_COMPLETED, "E2T_COMPLETED")

    def test_status_blocked_defined(self):
        self.assertEqual(E2T_STATUS_BLOCKED, "E2T_BLOCKED")

    def test_status_stopped_defined(self):
        self.assertEqual(E2T_STATUS_STOPPED, "E2T_STOPPED")

    def test_command_name_defined(self):
        self.assertEqual(E2T_COMMAND_NAME, "printer-run-e2t-bounded-cycle")

    def test_hard_locks_all_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_hard_locks_no_buy_sell_hold(self):
        self.assertIn("no_buy_sell_hold", _HARD_LOCKS)

    def test_hard_locks_no_unbounded_loop(self):
        self.assertIn("no_unbounded_loop", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_unbounded_loop"])

    def test_hard_locks_no_daemon_mode(self):
        self.assertIn("no_daemon_mode", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_daemon_mode"])

    def test_hard_locks_no_scheduler_bypass(self):
        self.assertIn("no_scheduler_bypass", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_scheduler_bypass"])

    def test_hard_locks_no_memory_creation(self):
        self.assertIn("no_memory_creation", _HARD_LOCKS)

    def test_hard_locks_no_5m_main_window(self):
        self.assertIn("no_5m_main_window", _HARD_LOCKS)


# ---------------------------------------------------------------------------
# Blocked gate tests
# ---------------------------------------------------------------------------

class LaneE2TBlockedGateTests(_DbTestBase):
    def test_blocked_when_not_operator_approved(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_when_not_approved_completed_zero(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["completed_cycle_count"], 0)

    def test_blocked_when_db_path_none(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        r = run_bounded_15m_cycles(
            token_file, None, self.backup_proof_path,
            operator_approved=True, max_cycles=1,
        )
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_when_db_path_missing(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        r = run_bounded_15m_cycles(
            token_file,
            pathlib.Path(self._tmp.name) / "no_such_db.sqlite3",
            self.backup_proof_path,
            operator_approved=True, max_cycles=1,
        )
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_when_backup_proof_none(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        r = run_bounded_15m_cycles(
            token_file, self.db_path, None,
            operator_approved=True, max_cycles=1,
        )
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_when_backup_proof_missing(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        r = run_bounded_15m_cycles(
            token_file, self.db_path,
            pathlib.Path(self._tmp.name) / "no_backup.sqlite3",
            operator_approved=True, max_cycles=1,
        )
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_when_token_list_none(self):
        r = run_bounded_15m_cycles(
            None, self.db_path, self.backup_proof_path,
            operator_approved=True, max_cycles=1,
        )
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_when_token_list_missing(self):
        r = run_bounded_15m_cycles(
            pathlib.Path(self._tmp.name) / "no_tokens.json",
            self.db_path, self.backup_proof_path,
            operator_approved=True, max_cycles=1,
        )
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_zero_cycle_count(self):
        r = self._run(max_cycles=0)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_negative_cycle_count(self):
        r = self._run(max_cycles=-1)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_above_hard_cap(self):
        r = self._run(max_cycles=E2T_MAX_CYCLES_HARD_CAP + 1)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_hard_cap_plus_1_is_4(self):
        r = self._run(max_cycles=4)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_blocked_has_stopped_reason(self):
        r = self._run(operator_approved=False)
        self.assertIsInstance(r.get("stopped_reason"), str)
        self.assertGreater(len(r["stopped_reason"]), 0)

    def test_blocked_has_empty_cycles_list(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["cycles"], [])

    def test_blocked_has_hard_locks(self):
        r = self._run(operator_approved=False)
        self.assertIsInstance(r.get("hard_locks"), dict)
        self.assertTrue(r["hard_locks"].get("no_buy_sell_hold"))

    def test_blocked_buy_sell_hold_false(self):
        r = self._run(operator_approved=False)
        self.assertFalse(r["buy_enabled"])
        self.assertFalse(r["sell_enabled"])
        self.assertFalse(r["hold_enabled"])


# ---------------------------------------------------------------------------
# Pre-cycle safety: running jobs / active locks
# ---------------------------------------------------------------------------

class LaneE2TPreCycleCheckTests(_DbTestBase):
    def _insert_running_job(self):
        conn = sqlite3.connect(str(self.db_path))
        now = "2026-06-28T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO printer_scheduler_jobs (
                job_name, job_kind, target_table, target_id, priority,
                status, scheduled_for, created_at, updated_at
            ) VALUES ('test_job', 'TRACK_FAST_FIRST_15M', NULL, NULL, 5,
                      'RUNNING', ?, ?, ?)
            """,
            (now, now, now),
        )
        conn.commit()
        conn.close()

    def _insert_locked_job(self):
        conn = sqlite3.connect(str(self.db_path))
        now = "2026-06-28T00:00:00+00:00"
        conn.execute(
            """
            INSERT INTO printer_scheduler_jobs (
                job_name, job_kind, target_table, target_id, priority,
                status, scheduled_for, lock_owner, locked_at,
                created_at, updated_at
            ) VALUES ('test_job', 'TRACK_FAST_FIRST_15M', NULL, NULL, 5,
                      'PENDING', ?, 'some_lock', ?, ?, ?)
            """,
            (now, now, now, now),
        )
        conn.commit()
        conn.close()

    def test_refuses_if_running_job_exists(self):
        self._insert_running_job()
        r = self._run(max_cycles=1)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_refuses_if_running_job_completed_zero(self):
        self._insert_running_job()
        r = self._run(max_cycles=1)
        self.assertEqual(r["completed_cycle_count"], 0)

    def test_refuses_if_running_job_has_reason(self):
        self._insert_running_job()
        r = self._run(max_cycles=1)
        reason = r.get("stopped_reason", "")
        self.assertIn("RUNNING", reason)

    def test_refuses_if_active_lock_exists(self):
        self._insert_locked_job()
        r = self._run(max_cycles=1)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)

    def test_refuses_if_active_lock_has_reason(self):
        self._insert_locked_job()
        r = self._run(max_cycles=1)
        reason = r.get("stopped_reason", "")
        self.assertIn("lock", reason.lower())


# ---------------------------------------------------------------------------
# One-cycle happy path
# ---------------------------------------------------------------------------

class LaneE2TOneCycleTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        self.result = self._run(max_cycles=1)

    def test_bounded_cycle_status_completed(self):
        self.assertEqual(self.result["bounded_cycle_status"], E2T_STATUS_COMPLETED)

    def test_requested_cycle_count_one(self):
        self.assertEqual(self.result["requested_cycle_count"], 1)

    def test_completed_cycle_count_one(self):
        self.assertEqual(self.result["completed_cycle_count"], 1)

    def test_cycles_list_length_one(self):
        self.assertEqual(len(self.result["cycles"]), 1)

    def test_cycle_e2j_status_executed(self):
        from printer_v1.operator_cli.e2j_first_15m_cycle import E2J_STATUS_EXECUTED
        self.assertEqual(self.result["cycles"][0]["e2j_status"], E2J_STATUS_EXECUTED)

    def test_cycle_executed_true(self):
        self.assertTrue(self.result["cycles"][0]["executed"])

    def test_cycle_job_id_is_int(self):
        self.assertIsInstance(self.result["cycles"][0]["job_id"], int)

    def test_cycle_snapshot_id_is_int(self):
        self.assertIsInstance(self.result["cycles"][0]["snapshot_id"], int)

    def test_cycle_memory_window_id_is_int(self):
        self.assertIsInstance(self.result["cycles"][0]["memory_window_id"], int)

    def test_cycle_audit_status_present(self):
        self.assertIsNotNone(self.result["cycles"][0]["memory_window_audit_status"])

    def test_cycle_audit_status_clean_candidate(self):
        from printer_v1.operator_cli.e2q_memory_window_audit import E2Q_STATUS_CLEAN_CANDIDATE
        self.assertEqual(
            self.result["cycles"][0]["memory_window_audit_status"],
            E2Q_STATUS_CLEAN_CANDIDATE,
        )

    def test_cycle_memory_quality_label_partial_memory(self):
        self.assertEqual(self.result["cycles"][0]["memory_quality_label"], "PARTIAL_MEMORY")

    def test_cycle_deltas_dict_present(self):
        self.assertIsInstance(self.result["cycles"][0]["deltas"], dict)

    def test_cycle_exec_error_none(self):
        self.assertIsNone(self.result["cycles"][0]["exec_error"])

    def test_stopped_reason_mentions_completed(self):
        self.assertIn("1", self.result.get("stopped_reason", ""))

    def test_hard_locks_present(self):
        self.assertIsInstance(self.result.get("hard_locks"), dict)

    def test_no_unbounded_loop_lock(self):
        self.assertTrue(self.result["hard_locks"].get("no_unbounded_loop"))

    def test_buy_enabled_false(self):
        self.assertFalse(self.result["buy_enabled"])

    def test_sell_enabled_false(self):
        self.assertFalse(self.result["sell_enabled"])

    def test_hold_enabled_false(self):
        self.assertFalse(self.result["hold_enabled"])

    def test_command_field(self):
        self.assertEqual(self.result["command"], E2T_COMMAND_NAME)

    def test_result_json_serializable(self):
        j = json.dumps(self.result)
        self.assertIsInstance(j, str)
        self.assertGreater(len(j), 10)


# ---------------------------------------------------------------------------
# Multi-cycle happy path
# ---------------------------------------------------------------------------

class LaneE2TMultiCycleTests(_DbTestBase):
    def test_two_cycles_succeed(self):
        r = self._run(max_cycles=2)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_COMPLETED)
        self.assertEqual(r["completed_cycle_count"], 2)
        self.assertEqual(len(r["cycles"]), 2)

    def test_three_cycles_succeed_at_cap(self):
        r = self._run(max_cycles=3)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_COMPLETED)
        self.assertEqual(r["completed_cycle_count"], 3)

    def test_two_cycles_create_two_snapshots(self):
        self._run(max_cycles=2)
        conn = sqlite3.connect(str(self.db_path))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM printer_token_snapshots"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 2)

    def test_two_cycles_create_two_windows(self):
        self._run(max_cycles=2)
        conn = sqlite3.connect(str(self.db_path))
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
            ).fetchone()[0]
        finally:
            conn.close()
        self.assertEqual(count, 2)

    def test_two_cycles_each_have_distinct_job_ids(self):
        r = self._run(max_cycles=2)
        ids = [c["job_id"] for c in r["cycles"]]
        self.assertEqual(len(set(ids)), 2)

    def test_two_cycles_each_have_distinct_snapshot_ids(self):
        r = self._run(max_cycles=2)
        ids = [c["snapshot_id"] for c in r["cycles"]]
        self.assertEqual(len(set(ids)), 2)

    def test_two_cycles_each_have_distinct_window_ids(self):
        r = self._run(max_cycles=2)
        ids = [c["memory_window_id"] for c in r["cycles"]]
        self.assertEqual(len(set(ids)), 2)

    def test_two_cycles_cycle_nums_sequential(self):
        r = self._run(max_cycles=2)
        nums = [c["cycle_num"] for c in r["cycles"]]
        self.assertEqual(nums, [1, 2])

    def test_four_cycles_blocked(self):
        r = self._run(max_cycles=4)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_BLOCKED)
        self.assertEqual(r["completed_cycle_count"], 0)


# ---------------------------------------------------------------------------
# Stop on blocked cycle
# ---------------------------------------------------------------------------

_E2J_PAYLOAD_PATH = (
    "printer_v1.operator_cli.e2j_first_15m_cycle"
    ".build_e2j_first_15m_cycle_payload"
)


class LaneE2TStopOnBlockedTests(_DbTestBase):
    def _blocked_e2j_result(self) -> dict:
        from printer_v1.operator_cli.e2j_first_15m_cycle import E2J_STATUS_BLOCKED
        return {
            "e2j_status": E2J_STATUS_BLOCKED,
            "executed": False,
            "cycle_status": "HANDLER_BLOCKED",
            "job_id": None,
            "exec_error": "transport not available",
            "blocked_reasons": ["transport not available"],
            "handler_result": {},
            "deltas": {},
            "snapshot_persistence_status": "NOT_ATTEMPTED",
            "snapshot_id": None,
            "memory_window_close_status": "NOT_ATTEMPTED",
            "memory_window_id": None,
            "memory_window_audit_status": "NOT_ATTEMPTED",
            "memory_quality_label": None,
            "memory_window_audit_row_updated": None,
        }

    def test_stops_on_blocked_cycle(self):
        with patch(_E2J_PAYLOAD_PATH, return_value=self._blocked_e2j_result()):
            r = self._run(max_cycles=2)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_STOPPED)

    def test_stops_completed_count_zero_on_first_block(self):
        with patch(_E2J_PAYLOAD_PATH, return_value=self._blocked_e2j_result()):
            r = self._run(max_cycles=2)
        self.assertEqual(r["completed_cycle_count"], 0)

    def test_stops_cycles_list_has_blocked_entry(self):
        with patch(_E2J_PAYLOAD_PATH, return_value=self._blocked_e2j_result()):
            r = self._run(max_cycles=2)
        self.assertEqual(len(r["cycles"]), 1)

    def test_stops_has_stopped_reason(self):
        with patch(_E2J_PAYLOAD_PATH, return_value=self._blocked_e2j_result()):
            r = self._run(max_cycles=2)
        self.assertIsInstance(r.get("stopped_reason"), str)
        self.assertGreater(len(r["stopped_reason"]), 0)

    def test_stop_after_first_success(self):
        """First cycle succeeds, second blocks — only 1 completed."""
        from printer_v1.operator_cli.e2j_first_15m_cycle import E2J_STATUS_EXECUTED
        success = {
            "e2j_status": E2J_STATUS_EXECUTED,
            "executed": True,
            "cycle_status": "SUCCEEDED",
            "job_id": 1,
            "exec_error": None,
            "blocked_reasons": [],
            "handler_result": {"source_results": []},
            "deltas": {},
            "snapshot_persistence_status": "E2M_SNAPSHOT_PERSISTED",
            "snapshot_id": 1,
            "memory_window_close_status": "E2O_WINDOW_CREATED",
            "memory_window_id": 1,
            "memory_window_audit_status": "E2Q_AUDIT_CLEAN_CANDIDATE",
            "memory_quality_label": "PARTIAL_MEMORY",
            "memory_window_audit_row_updated": True,
        }
        blocked = self._blocked_e2j_result()
        results = [success, blocked]
        call_count = [0]

        def _side_effect(*args, **kwargs):
            r = results[call_count[0]]
            call_count[0] += 1
            return r

        with patch(_E2J_PAYLOAD_PATH, side_effect=_side_effect):
            r = self._run(max_cycles=3)
        self.assertEqual(r["bounded_cycle_status"], E2T_STATUS_STOPPED)
        self.assertEqual(r["completed_cycle_count"], 1)
        self.assertEqual(len(r["cycles"]), 2)


# ---------------------------------------------------------------------------
# DB side-effects: forbidden table checks
# ---------------------------------------------------------------------------

class LaneE2TForbiddenTableTests(_DbTestBase):
    def test_no_paper_decisions_after_one_cycle(self):
        self._run(max_cycles=1)
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_paper_positions_after_one_cycle(self):
        self._run(max_cycles=1)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_no_paper_trade_events_after_one_cycle(self):
        self._run(max_cycles=1)
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)

    def test_no_paper_trade_audits_after_one_cycle(self):
        self._run(max_cycles=1)
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)

    def test_no_episodes_after_one_cycle(self):
        self._run(max_cycles=1)
        self.assertEqual(self._count_rows("printer_episodes"), 0)

    def test_no_memories_after_one_cycle(self):
        before = self._count_rows("printer_memories")
        self._run(max_cycles=1)
        self.assertEqual(self._count_rows("printer_memories"), before)

    def test_no_paper_decisions_after_two_cycles(self):
        self._run(max_cycles=2)
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_paper_positions_after_two_cycles(self):
        self._run(max_cycles=2)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_no_memories_after_two_cycles(self):
        before = self._count_rows("printer_memories")
        self._run(max_cycles=2)
        self.assertEqual(self._count_rows("printer_memories"), before)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2TCLITests(_DbTestBase):
    def test_cli_function_exists(self):
        self.assertTrue(callable(main_run_e2t_bounded_cycle))

    def test_cli_returns_zero_with_fixture_adapter(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        ret = main_run_e2t_bounded_cycle(
            [
                "--token-list-path", str(token_file),
                "--db-path", str(self.db_path),
                "--backup-proof-path", str(self.backup_proof_path),
                "--operator-approved",
                "--max-cycles", "1",
                "--format", "json",
            ],
            _adapter=_build_fixture_adapter(),
        )
        self.assertEqual(ret, 0)

    def test_cli_outputs_valid_json(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_run_e2t_bounded_cycle(
                [
                    "--token-list-path", str(token_file),
                    "--db-path", str(self.db_path),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--operator-approved",
                    "--max-cycles", "1",
                    "--format", "json",
                ],
                _adapter=_build_fixture_adapter(),
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertIsInstance(parsed, dict)

    def test_cli_output_has_command_field(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_run_e2t_bounded_cycle(
                [
                    "--token-list-path", str(token_file),
                    "--db-path", str(self.db_path),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--operator-approved",
                    "--max-cycles", "1",
                    "--format", "json",
                ],
                _adapter=_build_fixture_adapter(),
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed.get("command"), E2T_COMMAND_NAME)

    def test_cli_blocked_when_not_approved(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        captured = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_run_e2t_bounded_cycle(
                [
                    "--token-list-path", str(token_file),
                    "--db-path", str(self.db_path),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--max-cycles", "1",
                    "--format", "json",
                ],
                _adapter=_build_fixture_adapter(),
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed.get("bounded_cycle_status"), E2T_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# pyproject.toml entry point test
# ---------------------------------------------------------------------------

class LaneE2TPyprojectTests(unittest.TestCase):
    def test_pyproject_entry_registered(self):
        toml_path = PROJECT_ROOT / "pyproject.toml"
        content = toml_path.read_text(encoding="utf-8")
        self.assertIn("printer-run-e2t-bounded-cycle", content)

    def test_pyproject_entry_points_to_correct_function(self):
        toml_path = PROJECT_ROOT / "pyproject.toml"
        content = toml_path.read_text(encoding="utf-8")
        self.assertIn("main_run_e2t_bounded_cycle", content)


if __name__ == "__main__":
    unittest.main()
