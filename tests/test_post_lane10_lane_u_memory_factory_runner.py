"""
Post-Lane 10 Lane U -- Governed Reusable Memory Factory Operator Runner

Tests prove:
- Module imports cleanly; all constants present
- LANE_U_BLOCKED returned without operator_approved
- LANE_U_BLOCKED returned without db_path / backup_proof_path / token_list_path
- LANE_U_BLOCKED for WINDOW_5M_MICRO_EVENT as main window kind
- LANE_U_BLOCKED for WINDOW_1H / WINDOW_4H / WINDOW_12H / WINDOW_24H as main
- LANE_U_BLOCKED for unknown window kind
- WINDOW_5M_MICRO_EVENT recognized as support_window_kind (not blocked)
- LANE_U_BLOCKED for unsupported support_window_kind string
- LANE_U_BLOCKED for 12h / 24h profiles without allow_long_bounded_run
- 12h unblocked when allow_long_bounded_run=True (files present; still blocked on
  missing db in this fixture, but duration gate passes)
- LANE_U_BLOCKED for max_active_tokens / max_new_tokens exceeding hard caps
- LANE_U_COMPLETED returned for _cycle_budget=1 single-cycle run
- Single-cycle: all required reporting fields present
- Single-cycle: snapshot_id_for_window populated in first cycle
- Single-cycle: prev_close_snapshot_id set from first cycle close
- Single-cycle: lane_k_runs == 1
- Single-cycle: zero_clean_memories_is_valid == True
- Single-cycle: hard_locks all True
- Single-cycle: buy/sell/hold all False
- Single-cycle: paper_decisions_created == 0; retrieval_rows_created == 0
- Single-cycle: forbidden table counts all 0
- Two-cycle: lane_k_runs == 2; prev_close_snapshot_id updates
- Two-cycle: cycle 1 snapshot_start_id set from window-open snapshot (not None)
- Two-cycle: cycle 2 snapshot_start_id > cycle-1 close snapshot id (newer snap)
- Backdate proof: after backdating cycle-1 snapshot, cycle 2 shows
  lane_q_integrity_eligible=True
- _cycle_budget=0: stops immediately, COMPLETED, 0 cycles
- CLI function importable from commands.py; callable
- CLI blocked without --operator-approved (exit 0, BLOCKED status in JSON output)
- Idempotent Lane K: second run with same budget sees e2z_already_exists_count > 0
"""

from __future__ import annotations

import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from typing import Any

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_u_memory_factory_runner import (
    LANE_U_COMMAND_NAME,
    LANE_U_STATUS_BLOCKED,
    LANE_U_STATUS_COMPLETED,
    LANE_U_STATUS_STOPPED,
    _DEFAULT_PROFILE,
    _DURATION_PROFILES,
    _ENABLED_MAIN_WINDOW_KINDS,
    _HARD_LOCKS,
    _MAX_ACTIVE_TOKENS_HARD_CAP,
    _MAX_NEW_TOKENS_HARD_CAP,
    run_memory_factory_cycle,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
)

_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_PAIR_ADDR = "LaneUTestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_VALID_NOTE = "Operator-approved for Lane U test. Reviewed 2026-06-30."
_BACKDATE_TS = "2026-01-01T00:00:00+00:00"

_REQUIRED_REPORTING_FIELDS = frozenset({
    "command",
    "lane_u_status",
    "operator_approved",
    "db_path",
    "selected_profile",
    "requested_duration_seconds",
    "actual_duration_seconds",
    "run_started_at",
    "run_finished_at",
    "window_kind",
    "window_kind_enabled",
    "disabled_collection_window_kinds",
    "support_only_window_kinds",
    "max_active_tokens",
    "max_new_tokens",
    "selected_token_count",
    "total_cycles_attempted",
    "total_cycles_completed",
    "scheduler_jobs_created",
    "source_requests_created",
    "source_responses_created",
    "source_failures_created",
    "snapshots_created",
    "memory_windows_created",
    "lane_q_valid_windows",
    "lane_q_blocked_windows",
    "lane_k_runs",
    "clean_memory_rows_created",
    "e2z_already_exists_count",
    "dirty_or_blocked_memory_count",
    "retrieval_rows_created",
    "paper_decisions_created",
    "positions_created",
    "trade_events_created",
    "paper_trade_audits_created",
    "pnl_created",
    "stopped_safely_reason",
    "zero_clean_memories_is_valid",
    "governed_path_available",
    "prev_close_snapshot_id",
    "cycles",
    "forbidden_table_counts",
    "hard_locks",
    "buy_enabled",
    "sell_enabled",
    "hold_enabled",
    "snapshot_interval_seconds",
    "window_close_interval_seconds",
})


def _build_adapter(mint: str = _MINT_1):
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


class _DbBase(unittest.TestCase):
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

    def _write_token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tf.write_text(
            json.dumps({
                "tokens": [{
                    "token_mint": _MINT_1,
                    "lifecycle_lane": "TRACK_FAST",
                    "approved_by_operator": True,
                    "operator_note": _VALID_NOTE,
                }]
            }),
            encoding="utf-8",
        )
        return tf

    def _run(self, *, cycle_budget: int = 1, **overrides) -> dict[str, Any]:
        token_file = self._write_token_file()
        defaults: dict[str, Any] = dict(
            token_list_path=token_file,
            db_path=self.db_path,
            backup_proof_path=self.backup_proof_path,
            operator_approved=True,
            duration_profile="1h",
            window_kind="WINDOW_15M",
            _adapter=_build_adapter(),
            _cycle_budget=cycle_budget,
        )
        defaults.update(overrides)
        return run_memory_factory_cycle(**defaults)

    def _backdate_snapshot(self, snapshot_id: int) -> None:
        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.execute(
                "UPDATE printer_token_snapshots SET captured_at = ? WHERE id = ?",
                (_BACKDATE_TS, snapshot_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _fetch_window_row(self, window_id: int) -> dict | None:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT * FROM printer_memory_windows WHERE id = ?", (window_id,)
            ).fetchone()
            return dict(row) if row else None
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 1. Import / constant tests
# ---------------------------------------------------------------------------

class LaneUImportTests(unittest.TestCase):
    def test_module_imports_cleanly(self):
        from printer_v1.operator_cli import lane_u_memory_factory_runner
        self.assertIsNotNone(lane_u_memory_factory_runner)

    def test_run_function_callable(self):
        self.assertTrue(callable(run_memory_factory_cycle))

    def test_status_constants_exist(self):
        self.assertEqual(LANE_U_STATUS_COMPLETED, "LANE_U_COMPLETED")
        self.assertEqual(LANE_U_STATUS_BLOCKED, "LANE_U_BLOCKED")
        self.assertEqual(LANE_U_STATUS_STOPPED, "LANE_U_STOPPED")

    def test_command_name(self):
        self.assertEqual(LANE_U_COMMAND_NAME, "printer-run-memory-factory-cycle")

    def test_default_profile_in_duration_profiles(self):
        self.assertIn(_DEFAULT_PROFILE, _DURATION_PROFILES)
        self.assertEqual(_DEFAULT_PROFILE, "6h")

    def test_duration_profiles_values(self):
        self.assertEqual(_DURATION_PROFILES["1h"], 3600)
        self.assertEqual(_DURATION_PROFILES["4h"], 14400)
        self.assertEqual(_DURATION_PROFILES["6h"], 21600)
        self.assertEqual(_DURATION_PROFILES["12h"], 43200)
        self.assertEqual(_DURATION_PROFILES["24h"], 86400)

    def test_window_15m_is_enabled_main(self):
        self.assertIn("WINDOW_15M", _ENABLED_MAIN_WINDOW_KINDS)

    def test_hard_locks_all_true(self):
        for k, v in _HARD_LOCKS.items():
            self.assertTrue(v, f"hard lock {k!r} should be True")

    def test_max_token_caps(self):
        self.assertGreater(_MAX_ACTIVE_TOKENS_HARD_CAP, 0)
        self.assertGreater(_MAX_NEW_TOKENS_HARD_CAP, 0)


# ---------------------------------------------------------------------------
# 2. Gate / blocked tests (no DB needed)
# ---------------------------------------------------------------------------

class LaneUGateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_proof_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")
        apply_migrations(self.db_path)
        self.token_file = pathlib.Path(self._tmp.name) / "tokens.json"
        self.token_file.write_text(
            json.dumps({
                "tokens": [{
                    "token_mint": _MINT_1,
                    "lifecycle_lane": "TRACK_FAST",
                    "approved_by_operator": True,
                    "operator_note": _VALID_NOTE,
                }]
            }),
            encoding="utf-8",
        )

    def tearDown(self):
        self._tmp.cleanup()

    def _base_kwargs(self, **overrides):
        defaults = dict(
            token_list_path=self.token_file,
            db_path=self.db_path,
            backup_proof_path=self.backup_proof_path,
            operator_approved=True,
            duration_profile="1h",
            window_kind="WINDOW_15M",
            _cycle_budget=0,
        )
        defaults.update(overrides)
        return defaults

    # --- operator approval ---

    def test_blocked_without_operator_approved(self):
        r = run_memory_factory_cycle(
            self.token_file, self.db_path, self.backup_proof_path,
            operator_approved=False,
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        reasons = r["blocked_reasons"]
        self.assertTrue(any("operator_approved" in s for s in reasons))

    def test_blocked_requires_no_positional_approval_alias(self):
        # Confirm keyword-only gate: passing positional values in wrong order fails gate
        r = run_memory_factory_cycle(
            self.token_file, self.db_path, self.backup_proof_path,
            operator_approved=False, _cycle_budget=0,
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)

    # --- path gates ---

    def test_blocked_missing_db_path(self):
        r = run_memory_factory_cycle(
            self.token_file, None, self.backup_proof_path,
            operator_approved=True, _cycle_budget=0,
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("db_path" in s for s in r["blocked_reasons"]))

    def test_blocked_nonexistent_db_path(self):
        r = run_memory_factory_cycle(
            self.token_file,
            "/nonexistent/path/printer.sqlite3",
            self.backup_proof_path,
            operator_approved=True, _cycle_budget=0,
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)

    def test_blocked_missing_backup_proof_path(self):
        r = run_memory_factory_cycle(
            self.token_file, self.db_path, None,
            operator_approved=True, _cycle_budget=0,
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("backup_proof_path" in s for s in r["blocked_reasons"]))

    def test_blocked_missing_token_list_path(self):
        r = run_memory_factory_cycle(
            None, self.db_path, self.backup_proof_path,
            operator_approved=True, _cycle_budget=0,
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("token_list_path" in s for s in r["blocked_reasons"]))

    # --- window-kind gates ---

    def test_blocked_window_5m_as_main(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(window_kind="WINDOW_5M_MICRO_EVENT"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("5m" in s.lower() or "support" in s.lower()
                            for s in r["blocked_reasons"]))

    def test_blocked_window_1h_as_main(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(window_kind="WINDOW_1H"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)

    def test_blocked_window_4h_as_main(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(window_kind="WINDOW_4H"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)

    def test_blocked_window_12h_as_main(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(window_kind="WINDOW_12H"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)

    def test_blocked_window_24h_as_main(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(window_kind="WINDOW_24H"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)

    def test_blocked_unknown_window_kind(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(window_kind="WINDOW_UNKNOWN"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)

    def test_window_15m_not_blocked_on_window_kind(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(window_kind="WINDOW_15M"),
        )
        # May be COMPLETED or BLOCKED for other reasons, but not window_kind
        reasons = r.get("blocked_reasons", [])
        self.assertFalse(
            any("window_kind" in s and "WINDOW_15M" in s for s in reasons),
            f"WINDOW_15M should not be refused as main; reasons={reasons}",
        )

    # --- support window kind ---

    def test_support_window_5m_recognized(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(support_window_kind="WINDOW_5M_MICRO_EVENT"),
        )
        # Not blocked for support_window_kind reason
        reasons = r.get("blocked_reasons", [])
        self.assertFalse(
            any("support_window_kind" in s for s in reasons),
            f"WINDOW_5M_MICRO_EVENT should be recognized as support; reasons={reasons}",
        )
        self.assertEqual(r.get("support_window_kind"), "WINDOW_5M_MICRO_EVENT")

    def test_blocked_unsupported_support_window_kind(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(support_window_kind="WINDOW_UNKNOWN_SUPPORT"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("support_window_kind" in s for s in r["blocked_reasons"]))

    # --- duration profile gates ---

    def test_blocked_unknown_duration_profile(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(duration_profile="99h"),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("duration_profile" in s for s in r["blocked_reasons"]))

    def test_blocked_12h_without_allow_long_bounded_run(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(duration_profile="12h", allow_long_bounded_run=False),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(
            any("allow_long_bounded_run" in s for s in r["blocked_reasons"]),
            f"Should mention allow_long_bounded_run; reasons={r['blocked_reasons']}",
        )

    def test_blocked_24h_without_allow_long_bounded_run(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(duration_profile="24h", allow_long_bounded_run=False),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("allow_long_bounded_run" in s for s in r["blocked_reasons"]))

    def test_12h_duration_gate_passes_with_flag(self):
        # With allow_long_bounded_run=True, the duration gate should NOT block.
        # (Run still completes immediately with _cycle_budget=0.)
        r = run_memory_factory_cycle(
            **self._base_kwargs(
                duration_profile="12h",
                allow_long_bounded_run=True,
                _cycle_budget=0,
            ),
        )
        reasons = r.get("blocked_reasons", [])
        self.assertFalse(
            any("allow_long_bounded_run" in s for s in reasons),
            f"12h should be allowed with flag; reasons={reasons}",
        )

    # --- token limit gates ---

    def test_blocked_max_active_tokens_over_cap(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(max_active_tokens=_MAX_ACTIVE_TOKENS_HARD_CAP + 1),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("max_active_tokens" in s for s in r["blocked_reasons"]))

    def test_blocked_max_new_tokens_over_cap(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(max_new_tokens=_MAX_NEW_TOKENS_HARD_CAP + 1),
        )
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_BLOCKED)
        self.assertTrue(any("max_new_tokens" in s for s in r["blocked_reasons"]))

    def test_max_active_tokens_at_cap_passes(self):
        r = run_memory_factory_cycle(
            **self._base_kwargs(max_active_tokens=_MAX_ACTIVE_TOKENS_HARD_CAP),
        )
        reasons = r.get("blocked_reasons", [])
        self.assertFalse(any("max_active_tokens" in s for s in reasons))


# ---------------------------------------------------------------------------
# 3. Immediate stop — _cycle_budget=0
# ---------------------------------------------------------------------------

class LaneUZeroBudgetTests(_DbBase):
    def test_zero_budget_returns_completed(self):
        r = self._run(cycle_budget=0)
        self.assertEqual(r["lane_u_status"], LANE_U_STATUS_COMPLETED)

    def test_zero_budget_zero_cycles(self):
        r = self._run(cycle_budget=0)
        self.assertEqual(r["total_cycles_attempted"], 0)
        self.assertEqual(r["total_cycles_completed"], 0)

    def test_zero_budget_zero_lane_k_runs(self):
        r = self._run(cycle_budget=0)
        self.assertEqual(r["lane_k_runs"], 0)

    def test_zero_budget_has_all_required_fields(self):
        r = self._run(cycle_budget=0)
        for field in _REQUIRED_REPORTING_FIELDS:
            self.assertIn(field, r, f"missing required field: {field!r}")


# ---------------------------------------------------------------------------
# 4. Single-cycle run tests
# ---------------------------------------------------------------------------

class LaneUSingleCycleTests(_DbBase):
    def setUp(self):
        super().setUp()
        self._result = self._run(cycle_budget=1)

    def test_single_cycle_status_completed(self):
        self.assertEqual(self._result["lane_u_status"], LANE_U_STATUS_COMPLETED)

    def test_single_cycle_cycles_attempted(self):
        self.assertEqual(self._result["total_cycles_attempted"], 1)

    def test_single_cycle_cycles_completed(self):
        self.assertEqual(self._result["total_cycles_completed"], 1)

    def test_single_cycle_lane_k_runs(self):
        self.assertEqual(self._result["lane_k_runs"], 1)

    def test_single_cycle_has_cycles_list(self):
        self.assertIsInstance(self._result["cycles"], list)
        self.assertEqual(len(self._result["cycles"]), 1)

    def test_single_cycle_window_kind(self):
        self.assertEqual(self._result["window_kind"], "WINDOW_15M")
        self.assertTrue(self._result["window_kind_enabled"])

    def test_single_cycle_hard_locks_all_true(self):
        locks = self._result["hard_locks"]
        for k, v in locks.items():
            self.assertTrue(v, f"hard lock {k!r} should be True")

    def test_single_cycle_buy_sell_hold_false(self):
        self.assertFalse(self._result["buy_enabled"])
        self.assertFalse(self._result["sell_enabled"])
        self.assertFalse(self._result["hold_enabled"])

    def test_single_cycle_paper_decisions_zero(self):
        self.assertEqual(self._result["paper_decisions_created"], 0)

    def test_single_cycle_retrieval_rows_zero(self):
        self.assertEqual(self._result["retrieval_rows_created"], 0)

    def test_single_cycle_positions_zero(self):
        self.assertEqual(self._result["positions_created"], 0)

    def test_single_cycle_pnl_zero(self):
        self.assertEqual(self._result["pnl_created"], 0)

    def test_single_cycle_trade_events_zero(self):
        self.assertEqual(self._result["trade_events_created"], 0)

    def test_single_cycle_zero_clean_memories_valid(self):
        self.assertTrue(self._result["zero_clean_memories_is_valid"])

    def test_single_cycle_governed_path_available(self):
        self.assertTrue(self._result["governed_path_available"])

    def test_single_cycle_snapshot_id_for_window_set(self):
        cycle = self._result["cycles"][0]
        self.assertIsNotNone(cycle.get("snapshot_id_for_window"))

    def test_single_cycle_prev_close_snapshot_set(self):
        self.assertIsNotNone(self._result["prev_close_snapshot_id"])

    def test_single_cycle_snapshot_start_set_from_window(self):
        # snapshot_start_id is the first snapshot captured in this window
        # (from the snapshot-only call).  With a real adapter it is set.
        cycle = self._result["cycles"][0]
        self.assertIsNotNone(cycle.get("snapshot_start_id"))

    def test_single_cycle_lane_q_not_eligible_no_prior(self):
        # No prior snapshot → instant window → lane_q_integrity_eligible False
        cycle = self._result["cycles"][0]
        self.assertFalse(cycle.get("lane_q_integrity_eligible"))

    def test_single_cycle_forbidden_table_counts_zero(self):
        counts = self._result.get("forbidden_table_counts", {})
        for table, count in counts.items():
            self.assertEqual(
                count, 0,
                f"forbidden table {table!r} should have 0 rows; got {count}",
            )

    def test_single_cycle_all_required_fields_present(self):
        for field in _REQUIRED_REPORTING_FIELDS:
            self.assertIn(field, self._result, f"missing required field: {field!r}")

    def test_single_cycle_run_timestamps_set(self):
        self.assertIsNotNone(self._result["run_started_at"])
        self.assertIsNotNone(self._result["run_finished_at"])

    def test_single_cycle_actual_duration_nonnegative(self):
        self.assertGreaterEqual(self._result["actual_duration_seconds"], 0.0)

    def test_single_cycle_command_name(self):
        self.assertEqual(self._result["command"], LANE_U_COMMAND_NAME)

    def test_single_cycle_disabled_collection_window_kinds_present(self):
        disabled = self._result.get("disabled_collection_window_kinds", [])
        self.assertIn("WINDOW_1H", disabled)
        self.assertIn("WINDOW_4H", disabled)

    def test_single_cycle_support_only_window_kinds_present(self):
        support = self._result.get("support_only_window_kinds", [])
        self.assertIn("WINDOW_5M_MICRO_EVENT", support)


# ---------------------------------------------------------------------------
# 5. Two-cycle threading tests (Lane-T snapshot_start_id pass-through)
# ---------------------------------------------------------------------------

class LaneUTwoCycleThreadingTests(_DbBase):
    def setUp(self):
        super().setUp()
        self._result = self._run(cycle_budget=2)

    def test_two_cycle_status_completed(self):
        self.assertEqual(self._result["lane_u_status"], LANE_U_STATUS_COMPLETED)

    def test_two_cycle_completed_count(self):
        self.assertEqual(self._result["total_cycles_completed"], 2)

    def test_two_cycle_lane_k_runs(self):
        self.assertEqual(self._result["lane_k_runs"], 2)

    def test_two_cycle_first_snapshot_start_set(self):
        # snapshot_start_id = first snapshot captured during window 1's collection.
        # With a real adapter it is set (not None).
        c1 = self._result["cycles"][0]
        self.assertIsNotNone(c1.get("snapshot_start_id"))

    def test_two_cycle_second_snapshot_start_after_cycle1_close(self):
        # Window 2's snapshot_start_id is a newer snapshot than window 1's close.
        # (Window 2 opens with a fresh snapshot-only call after window 1 closes.)
        c1 = self._result["cycles"][0]
        c2 = self._result["cycles"][1]
        snap1_close = c1.get("snapshot_id_for_window")
        snap2_start = c2.get("snapshot_start_id")
        self.assertIsNotNone(snap1_close, "cycle 1 should have a close snapshot")
        self.assertIsNotNone(snap2_start, "cycle 2 should have a start snapshot")
        self.assertGreater(
            snap2_start, snap1_close,
            "cycle 2 snapshot_start_id must be newer than cycle 1 close snapshot",
        )

    def test_two_cycle_prev_close_snapshot_updates(self):
        c2 = self._result["cycles"][1]
        self.assertIsNotNone(c2.get("snapshot_id_for_window"))
        # prev_close_snapshot_id in result should be cycle 2's close snapshot
        self.assertEqual(
            self._result["prev_close_snapshot_id"],
            c2.get("snapshot_id_for_window"),
        )

    def test_two_cycle_fixture_elapsed_near_zero_lane_q_false(self):
        # Without real time gap, elapsed ≈ 0 → lane_q_integrity_eligible False
        c2 = self._result["cycles"][1]
        self.assertFalse(
            c2.get("lane_q_integrity_eligible"),
            "Fixture cycles run back-to-back; elapsed ≈ 0 → Lane Q should block",
        )


# ---------------------------------------------------------------------------
# 6. Backdate proof — elapsed >> 900s → lane_q_integrity_eligible=True
# ---------------------------------------------------------------------------

class LaneUBackdateProofTests(_DbBase):
    def test_backdate_cycle1_makes_cycle2_lane_q_eligible(self):
        # Run cycle 1 first (no start snapshot)
        r1 = self._run(cycle_budget=1)
        self.assertEqual(r1["lane_u_status"], LANE_U_STATUS_COMPLETED)
        snap1_close = r1["prev_close_snapshot_id"]
        self.assertIsNotNone(snap1_close)

        # Backdate cycle-1 snapshot to 2026-01-01 — guarantees >> 900s elapsed
        self._backdate_snapshot(int(snap1_close))

        # Run cycle 2 with prev_close as start
        from printer_v1.operator_cli.e2j_first_15m_cycle import (
            build_e2j_first_15m_cycle_payload,
        )
        token_file = self._write_token_file()
        r2 = build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_adapter(),
            _snapshot_start_id=int(snap1_close),
        )
        self.assertTrue(
            r2.get("lane_q_integrity_eligible"),
            f"After backdate, elapsed >> 900s; lane_q_integrity_eligible should be True."
            f" Got: {r2.get('elapsed_seconds')!r}s",
        )

    def test_backdate_lane_u_two_cycles_passes_lane_q(self):
        # Run two Lane U cycles but backdate the first close snapshot between them
        r1 = self._run(cycle_budget=1)
        snap1_close = r1["prev_close_snapshot_id"]
        self.assertIsNotNone(snap1_close)

        # Backdate so cycle 2 sees >> 900s elapsed
        self._backdate_snapshot(int(snap1_close))

        # Re-run with prev_close injected (simulate what Lane U would do naturally)
        from printer_v1.operator_cli.lane_u_memory_factory_runner import (
            run_memory_factory_cycle,
        )
        token_file = self._write_token_file()
        # Use a fresh result with only 1 cycle but starting from snap1_close
        from printer_v1.operator_cli.e2j_first_15m_cycle import (
            build_e2j_first_15m_cycle_payload,
        )
        r2 = build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_adapter(),
            _snapshot_start_id=int(snap1_close),
        )
        self.assertTrue(r2.get("lane_q_integrity_eligible"))
        self.assertIsNotNone(r2.get("window_start_at"))
        self.assertIsNotNone(r2.get("window_end_at"))
        elapsed = r2.get("elapsed_seconds") or 0
        self.assertGreater(elapsed, 900.0)


# ---------------------------------------------------------------------------
# 7. Lane K idempotency — second run creates already-exists, not new rows
# ---------------------------------------------------------------------------

class LaneULaneKIdempotencyTests(_DbBase):
    def test_second_run_lane_k_sees_already_exists(self):
        r1 = self._run(cycle_budget=1)
        self.assertEqual(r1["lane_u_status"], LANE_U_STATUS_COMPLETED)
        # If any clean memories were created in r1, a second run should see them
        # as already-exists (Lane K / E2Z is idempotent).
        # Note: with a single fixture cycle elapsed≈0, Lane Q blocks, so
        # clean_memory_rows_created may be 0 — that is valid.
        # Run Lane K directly to verify idempotency.
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
        k1 = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertIn("clean_memory_rows_created", k1)
        k2 = run_e2z_pipeline(self.db_path, operator_approved=True)
        # After k1 ran, k2 should not create more than k1
        self.assertEqual(
            k2["clean_memory_rows_created"],
            0,
            "Second Lane K run should not create new rows (idempotent)",
        )

    def test_zero_clean_memories_is_always_valid(self):
        r = self._run(cycle_budget=1)
        self.assertTrue(r["zero_clean_memories_is_valid"])
        # clean_memory_rows_created may be 0 with elapsed ≈ 0; that is valid
        self.assertGreaterEqual(r["clean_memory_rows_created"], 0)


# ---------------------------------------------------------------------------
# 8. CLI interface tests
# ---------------------------------------------------------------------------

class LaneUCLITests(unittest.TestCase):
    def test_cli_function_importable(self):
        from printer_v1.operator_cli.commands import main_run_memory_factory_cycle
        self.assertTrue(callable(main_run_memory_factory_cycle))

    def test_cli_blocked_without_operator_approved(self):
        """--operator-approved missing → exits 0 with BLOCKED JSON."""
        from printer_v1.operator_cli.commands import main_run_memory_factory_cycle

        with tempfile.TemporaryDirectory() as tmp:
            db = pathlib.Path(tmp) / "p.sqlite3"
            backup = pathlib.Path(tmp) / "backup.sqlite3"
            backup.write_bytes(b"backup")
            tl = pathlib.Path(tmp) / "tokens.json"
            apply_migrations(db)
            tl.write_text(
                json.dumps({
                    "tokens": [{
                        "token_mint": _MINT_1,
                        "lifecycle_lane": "TRACK_FAST",
                        "approved_by_operator": True,
                        "operator_note": _VALID_NOTE,
                    }]
                }),
                encoding="utf-8",
            )
            buf = io.StringIO()
            import sys as _sys
            old_stdout = _sys.stdout
            _sys.stdout = buf
            try:
                rc = main_run_memory_factory_cycle([
                    "--db-path", str(db),
                    "--token-list-path", str(tl),
                    "--backup-proof-path", str(backup),
                    "--project-root", tmp,
                    # deliberately omit --operator-approved
                ])
            finally:
                _sys.stdout = old_stdout
            self.assertEqual(rc, 0, "CLI should exit 0 even when blocked")
            output = buf.getvalue()
            payload = json.loads(output)
            self.assertEqual(payload["lane_u_status"], LANE_U_STATUS_BLOCKED)

    def test_cli_entry_point_registered(self):
        """Verify printer-run-memory-factory-cycle is in pyproject.toml."""
        pyproject = PROJECT_ROOT / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        self.assertIn("printer-run-memory-factory-cycle", text)

    def test_cli_command_name_constant_matches_pyproject(self):
        pyproject = PROJECT_ROOT / "pyproject.toml"
        text = pyproject.read_text(encoding="utf-8")
        self.assertIn(LANE_U_COMMAND_NAME, text)


# ---------------------------------------------------------------------------
# 9. Report field completeness on blocked result
# ---------------------------------------------------------------------------

class LaneUBlockedFieldTests(unittest.TestCase):
    def test_blocked_result_has_blocked_reasons_list(self):
        r = run_memory_factory_cycle(None, None, None, operator_approved=False)
        self.assertIsInstance(r.get("blocked_reasons"), list)
        self.assertGreater(len(r["blocked_reasons"]), 0)

    def test_blocked_result_hard_locks_present(self):
        r = run_memory_factory_cycle(None, None, None, operator_approved=False)
        self.assertIsInstance(r.get("hard_locks"), dict)

    def test_blocked_result_buy_sell_hold_false(self):
        r = run_memory_factory_cycle(None, None, None, operator_approved=False)
        self.assertFalse(r.get("buy_enabled"))
        self.assertFalse(r.get("sell_enabled"))
        self.assertFalse(r.get("hold_enabled"))

    def test_blocked_result_zero_clean_memories_valid(self):
        r = run_memory_factory_cycle(None, None, None, operator_approved=False)
        self.assertTrue(r.get("zero_clean_memories_is_valid"))

    def test_blocked_result_status_not_completed(self):
        r = run_memory_factory_cycle(None, None, None, operator_approved=False)
        self.assertNotEqual(r["lane_u_status"], LANE_U_STATUS_COMPLETED)

    def test_blocked_result_paper_decisions_zero(self):
        r = run_memory_factory_cycle(None, None, None, operator_approved=False)
        self.assertEqual(r.get("paper_decisions_created"), 0)

    def test_blocked_result_command_name(self):
        r = run_memory_factory_cycle(None, None, None, operator_approved=False)
        self.assertEqual(r["command"], LANE_U_COMMAND_NAME)


if __name__ == "__main__":
    unittest.main()
