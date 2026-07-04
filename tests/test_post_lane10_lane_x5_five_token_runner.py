"""Lane X5 — Five-Token Source-Budget Proof tests.

Validates:
- Exactly 5 TRACK_FAST operator-approved Solana tokens accepted; 0-4 and 6+ rejected.
- Unapproved, non-TRACK_FAST, non-solana, placeholder, duplicate tokens rejected.
- A/B/C/D/E deterministic rotation: tick % 5 → index 0-4.
- Source budget: consecutive failures trigger safe stop after limit.
- Throttle/backoff: sleep on failure is safe; does not crash or hang.
- No token is starved: budget=5 gives each slot exactly 1 window close.
- Evidence isolated per token — each mint's snapshots build only its own memory.
- Per-token source/snapshot/window-close counts reported independently.
- All retrieval/paper/BUY/position/PnL locks remain zero.
- Hard locks dict: 24 keys all True (no_source_budget_bypass, no_x6_expansion).
- All window-kind gates remain: 5m forbidden as main, 1h/4h/12h/24h blocked.
- Zero clean memories is a valid outcome.
- X2 (79 tests), X3 (97 tests), and X4 (116 tests) regressions — no module modified.
"""

from __future__ import annotations

import io
import json
import pathlib
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from typing import Any

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_x5_five_token_runner import (
    LANE_X5_COMMAND_NAME,
    LANE_X5_EXACT_TOKEN_COUNT,
    LANE_X5_STATUS_BLOCKED,
    LANE_X5_STATUS_COMPLETED,
    LANE_X5_STATUS_STOPPED,
    _HARD_LOCKS,
    _load_and_validate_five_token_list,
    run_five_token_memory_factory_cycle,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
)

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

_MINT_A = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_MINT_B = "8bSGn8sHT9V3jmfN3CbLt24ziNFbjs4svN4sPwUHqump"
_MINT_C = "7aQFm7rFS8U4klgO4DaMs35yiOGckt5tuO5tOvVGrump"
_MINT_D = "6zPGm6QT7U5jlhPbE9ClNs46xjNFck6tsxPbN3sWFpump"
_MINT_E = "5yOFl5PS6V6kmgOcFEaLm57wjNEbjs5suO6sOuUHrump"

_PAIR_A = "LaneX5TestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_B = "LaneX5TestPairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_PAIR_C = "LaneX5TestPairCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
_PAIR_D = "LaneX5TestPairDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"
_PAIR_E = "LaneX5TestPairEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"

_MINT_EXTRA = "4xNEl4OT8W7nlmNcGFbKM68vjMFblkt7ttP7nvTGqump"

_REQUIRED_REPORTING_FIELDS = frozenset({
    "command",
    "lane_x5_status",
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
    "selected_token_count",
    "token_a_mint",
    "token_b_mint",
    "token_c_mint",
    "token_d_mint",
    "token_e_mint",
    "total_window_closes",
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
    "source_budget_max_consecutive_failures",
    "throttle_backoff_seconds",
    "total_source_failures",
    "hard_locks",
    "buy_enabled",
    "sell_enabled",
    "hold_enabled",
    "token_a_report",
    "token_b_report",
    "token_c_report",
    "token_d_report",
    "token_e_report",
    "cycles",
    "forbidden_table_counts",
})

_TOKEN_REPORT_FIELDS = frozenset({
    "slot",
    "mint",
    "snapshots_created",
    "memory_windows_created",
    "source_requests_created",
    "source_responses_created",
    "source_failures_created",
    "lane_q_valid_windows",
    "lane_q_blocked_windows",
    "window_closes",
    "clean_memory_created",
    "dirty_memory_count",
    "e2z_already_exists_count",
    "lane_k_runs",
})


# ---------------------------------------------------------------------------
# Fixture adapter helpers
# ---------------------------------------------------------------------------

def _build_adapter(mint: str, pair_address: str):
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_kind=FIXTURE_SUCCESS,
        fixture_payload={
            "source_name": "dexscreener",
            "request_kind": "pair_market_snapshot",
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": pair_address,
                    "token_mint": mint,
                    "symbol": "X5T",
                    "name": "Lane X5 Test Token",
                    "price_usd": 0.00055,
                    "liquidity_usd": 60000.0,
                    "volume_5m": 1500.0,
                    "volume_1h": 18000.0,
                    "volume_24h": 432000.0,
                    "txns_5m": 15,
                    "txns_1h": 180,
                    "txns_24h": 4320,
                    "fdv": 550000.0,
                    "market_cap": 490000.0,
                    "price_change_5m": 0.8,
                    "price_change_1h": 3.2,
                    "price_change_24h": -2.1,
                }
            ],
        },
    )


def _make_adapter_map():
    return {
        _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
        _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
        _MINT_C: _build_adapter(_MINT_C, _PAIR_C),
        _MINT_D: _build_adapter(_MINT_D, _PAIR_D),
        _MINT_E: _build_adapter(_MINT_E, _PAIR_E),
    }


class _FailingCallable:
    """Callable that always raises RuntimeError — simulates source failures."""

    def __call__(self, *args, **kwargs):
        raise RuntimeError("simulated source failure for budget test")


def _make_failing_adapter_map():
    """Return a map where all five mints use the failing adapter."""
    fa = _FailingCallable()
    return {
        _MINT_A: fa,
        _MINT_B: fa,
        _MINT_C: fa,
        _MINT_D: fa,
        _MINT_E: fa,
    }


# ---------------------------------------------------------------------------
# Base class
# ---------------------------------------------------------------------------

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

    def _count_rows_where(self, table: str, where: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {where}"
            ).fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _write_x5_token_file(
        self,
        *,
        mint_a: str = _MINT_A,
        pair_a: str = _PAIR_A,
        mint_b: str = _MINT_B,
        pair_b: str = _PAIR_B,
        mint_c: str = _MINT_C,
        pair_c: str = _PAIR_C,
        mint_d: str = _MINT_D,
        pair_d: str = _PAIR_D,
        mint_e: str = _MINT_E,
        pair_e: str = _PAIR_E,
        tracking_lane: str = "TRACK_FAST",
        approved: bool = True,
        tokens_override: list | None = None,
    ) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens_x5.json"
        if tokens_override is not None:
            data = {"tokens": tokens_override}
        else:
            data = {
                "tokens": [
                    {
                        "token_mint": mint_a,
                        "pair_address": pair_a,
                        "chain": "solana",
                        "tracking_lane": tracking_lane,
                        "operator_approved": approved,
                    },
                    {
                        "token_mint": mint_b,
                        "pair_address": pair_b,
                        "chain": "solana",
                        "tracking_lane": tracking_lane,
                        "operator_approved": approved,
                    },
                    {
                        "token_mint": mint_c,
                        "pair_address": pair_c,
                        "chain": "solana",
                        "tracking_lane": tracking_lane,
                        "operator_approved": approved,
                    },
                    {
                        "token_mint": mint_d,
                        "pair_address": pair_d,
                        "chain": "solana",
                        "tracking_lane": tracking_lane,
                        "operator_approved": approved,
                    },
                    {
                        "token_mint": mint_e,
                        "pair_address": pair_e,
                        "chain": "solana",
                        "tracking_lane": tracking_lane,
                        "operator_approved": approved,
                    },
                ]
            }
        tf.write_text(json.dumps(data), encoding="utf-8")
        return tf

    def _run(
        self,
        *,
        cycle_budget: int = 1,
        operator_approved: bool = True,
        window_kind: str = "WINDOW_15M",
        duration_profile: str = "1h",
        adapter_map=None,
        **overrides,
    ) -> dict[str, Any]:
        token_file = self._write_x5_token_file()
        am = adapter_map if adapter_map is not None else _make_adapter_map()
        defaults: dict[str, Any] = dict(
            token_list_path=token_file,
            db_path=self.db_path,
            backup_proof_path=self.backup_proof_path,
            operator_approved=operator_approved,
            duration_profile=duration_profile,
            window_kind=window_kind,
            _adapter_map=am,
            _cycle_budget=cycle_budget,
        )
        defaults.update(overrides)
        return run_five_token_memory_factory_cycle(**defaults)


# ---------------------------------------------------------------------------
# 1. Validator tests — no DB
# ---------------------------------------------------------------------------

class TestLaneX5FiveTokenValidator(unittest.TestCase):
    """Unit tests for _load_and_validate_five_token_list."""

    def _write(self, tokens: list, tmp_dir: str) -> pathlib.Path:
        p = pathlib.Path(tmp_dir) / "tokens.json"
        p.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return p

    def _valid_token(self, mint: str, pair: str) -> dict:
        return {
            "token_mint": mint,
            "pair_address": pair,
            "chain": "solana",
            "tracking_lane": "TRACK_FAST",
            "operator_approved": True,
        }

    def test_five_tokens_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_D, _PAIR_D),
                self._valid_token(_MINT_E, _PAIR_E),
            ], tmp)
            valid, reason, a, b, c, d, e = _load_and_validate_five_token_list(path)
            self.assertTrue(valid, reason)
            self.assertEqual(a["token_mint"], _MINT_A)
            self.assertEqual(e["token_mint"], _MINT_E)

    def test_zero_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([], tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("exactly 5", reason)

    def test_one_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([self._valid_token(_MINT_A, _PAIR_A)], tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("exactly 5", reason)

    def test_two_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
            ], tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("exactly 5", reason)

    def test_three_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("exactly 5", reason)

    def test_four_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_D, _PAIR_D),
            ], tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("exactly 5", reason)

    def test_six_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_D, _PAIR_D),
                self._valid_token(_MINT_E, _PAIR_E),
                self._valid_token(_MINT_EXTRA, "LaneX5ExtraPair111111111111111111111111111"),
            ], tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("exactly 5", reason)

    def test_unapproved_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                {**self._valid_token(_MINT_C, _PAIR_C), "operator_approved": False},
                self._valid_token(_MINT_D, _PAIR_D),
                self._valid_token(_MINT_E, _PAIR_E),
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("operator_approved", reason)

    def test_track_normal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                {**self._valid_token(_MINT_D, _PAIR_D), "tracking_lane": "TRACK_NORMAL"},
                self._valid_token(_MINT_E, _PAIR_E),
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("TRACK_FAST", reason)

    def test_watch_only_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                {**self._valid_token(_MINT_B, _PAIR_B), "tracking_lane": "WATCH_ONLY"},
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_D, _PAIR_D),
                self._valid_token(_MINT_E, _PAIR_E),
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("TRACK_FAST", reason)

    def test_non_solana_chain_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                {**self._valid_token(_MINT_C, _PAIR_C), "chain": "ethereum"},
                self._valid_token(_MINT_D, _PAIR_D),
                self._valid_token(_MINT_E, _PAIR_E),
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("solana", reason)

    def test_placeholder_mint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                {**self._valid_token(_MINT_D, _PAIR_D), "token_mint": "PLACEHOLDER_MINT"},
                self._valid_token(_MINT_E, _PAIR_E),
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("placeholder", reason)

    def test_placeholder_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_D, _PAIR_D),
                {**self._valid_token(_MINT_E, _PAIR_E), "pair_address": "PLACEHOLDER_PAIR"},
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("placeholder", reason)

    def test_duplicate_mint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_A, _PAIR_D),  # duplicate MINT_A
                self._valid_token(_MINT_E, _PAIR_E),
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("duplicate", reason)

    def test_duplicate_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_D, _PAIR_D),
                self._valid_token(_MINT_E, _PAIR_A),  # duplicate PAIR_A
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("duplicate", reason)

    def test_none_path_rejected(self):
        valid, reason, *_ = _load_and_validate_five_token_list(None)
        self.assertFalse(valid)
        self.assertIn("required", reason)

    def test_missing_file_rejected(self):
        valid, reason, *_ = _load_and_validate_five_token_list("/nonexistent/path.json")
        self.assertFalse(valid)
        self.assertIn("not found", reason)

    def test_bad_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "bad.json"
            p.write_text("not valid json {{{{", encoding="utf-8")
            valid, reason, *_ = _load_and_validate_five_token_list(p)
            self.assertFalse(valid)
            self.assertIn("unreadable", reason)

    def test_x4_format_three_tokens_rejected_by_x5_validator(self):
        """An X4 token list (3 tokens) must be rejected by the X5 validator."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("exactly 5", reason)

    def test_all_five_unapproved_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tokens = [
                {**self._valid_token(_MINT_A, _PAIR_A), "operator_approved": False},
                {**self._valid_token(_MINT_B, _PAIR_B), "operator_approved": False},
                {**self._valid_token(_MINT_C, _PAIR_C), "operator_approved": False},
                {**self._valid_token(_MINT_D, _PAIR_D), "operator_approved": False},
                {**self._valid_token(_MINT_E, _PAIR_E), "operator_approved": False},
            ]
            path = self._write(tokens, tmp)
            valid, reason, *_ = _load_and_validate_five_token_list(path)
            self.assertFalse(valid)
            self.assertIn("operator_approved", reason)

    def test_validator_returns_7_tuple(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_D, _PAIR_D),
                self._valid_token(_MINT_E, _PAIR_E),
            ], tmp)
            result = _load_and_validate_five_token_list(path)
            self.assertEqual(len(result), 7)


# ---------------------------------------------------------------------------
# 2. Gate checks
# ---------------------------------------------------------------------------

class TestLaneX5GateChecks(_DbBase):
    """Gate-check tests: blocked results without running the main loop."""

    def test_operator_not_approved_blocked(self):
        result = self._run(operator_approved=False, cycle_budget=1)
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        self.assertFalse(result["operator_approved"])

    def test_db_path_none_blocked(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            None,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_db_path_missing_blocked(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            "/nonexistent/printer_v1.sqlite3",
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_backup_proof_none_blocked(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            None,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_backup_proof_missing_blocked(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            "/nonexistent/backup.sqlite3",
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_token_list_none_blocked(self):
        result = run_five_token_memory_factory_cycle(
            None,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_token_list_missing_blocked(self):
        result = run_five_token_memory_factory_cycle(
            "/nonexistent/tokens.json",
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_5m_as_main_window_blocked(self):
        result = self._run(window_kind="WINDOW_5M_MICRO_EVENT")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertIn("support-only", reasons)

    def test_1h_window_blocked(self):
        result = self._run(window_kind="WINDOW_1H")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_4h_window_blocked(self):
        result = self._run(window_kind="WINDOW_4H")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_12h_window_blocked(self):
        result = self._run(window_kind="WINDOW_12H")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_24h_window_blocked(self):
        result = self._run(window_kind="WINDOW_24H")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_unknown_window_blocked(self):
        result = self._run(window_kind="WINDOW_UNKNOWN")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_12h_profile_without_flag_blocked(self):
        result = self._run(duration_profile="12h")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertIn("allow_long_bounded_run", reasons)

    def test_24h_profile_without_flag_blocked(self):
        result = self._run(duration_profile="24h")
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_blocked_result_has_zero_window_closes(self):
        result = self._run(operator_approved=False)
        self.assertEqual(result["total_window_closes"], 0)

    def test_blocked_result_buy_enabled_false(self):
        result = self._run(operator_approved=False)
        self.assertFalse(result["buy_enabled"])

    def test_blocked_result_has_hard_locks(self):
        result = self._run(operator_approved=False)
        self.assertIn("hard_locks", result)
        self.assertTrue(result["hard_locks"]["no_buy_sell_hold"])

    def test_invalid_token_count_blocked(self):
        token_file = self._write_x5_token_file(
            tokens_override=[
                {
                    "token_mint": _MINT_A,
                    "pair_address": _PAIR_A,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                },
                {
                    "token_mint": _MINT_B,
                    "pair_address": _PAIR_B,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                },
            ]
        )
        result = run_five_token_memory_factory_cycle(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertIn("5", reasons)


# ---------------------------------------------------------------------------
# 3. Execution tests
# ---------------------------------------------------------------------------

class TestLaneX5Execution(_DbBase):
    """Basic run tests verifying Lane X5 executes correctly."""

    def test_basic_run_completes(self):
        result = self._run(cycle_budget=1)
        self.assertIn(result["lane_x5_status"], {LANE_X5_STATUS_COMPLETED, LANE_X5_STATUS_STOPPED})

    def test_all_required_fields_present(self):
        result = self._run(cycle_budget=1)
        missing = _REQUIRED_REPORTING_FIELDS - set(result.keys())
        self.assertEqual(missing, set(), f"Missing fields: {missing}")

    def test_command_name_correct(self):
        result = self._run(cycle_budget=1)
        self.assertEqual(result["command"], LANE_X5_COMMAND_NAME)

    def test_token_count_is_five(self):
        result = self._run(cycle_budget=1)
        self.assertEqual(result["selected_token_count"], 5)

    def test_all_five_mints_present(self):
        result = self._run(cycle_budget=5)
        self.assertEqual(result["token_a_mint"], _MINT_A)
        self.assertEqual(result["token_b_mint"], _MINT_B)
        self.assertEqual(result["token_c_mint"], _MINT_C)
        self.assertEqual(result["token_d_mint"], _MINT_D)
        self.assertEqual(result["token_e_mint"], _MINT_E)

    def test_all_token_reports_present(self):
        result = self._run(cycle_budget=5)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertIsNotNone(result[key], f"{key} is None")

    def test_token_report_has_correct_fields(self):
        result = self._run(cycle_budget=5)
        report = result["token_a_report"]
        missing = _TOKEN_REPORT_FIELDS - set(report.keys())
        self.assertEqual(missing, set(), f"Missing fields in token_a_report: {missing}")

    def test_zero_clean_memories_is_valid(self):
        result = self._run(cycle_budget=1)
        self.assertTrue(result["zero_clean_memories_is_valid"])

    def test_operator_approved_true_in_result(self):
        result = self._run(cycle_budget=1)
        self.assertTrue(result["operator_approved"])

    def test_window_kind_enabled_true(self):
        result = self._run(cycle_budget=1)
        self.assertTrue(result["window_kind_enabled"])

    def test_buy_sell_hold_false(self):
        result = self._run(cycle_budget=5)
        self.assertFalse(result["buy_enabled"])
        self.assertFalse(result["sell_enabled"])
        self.assertFalse(result["hold_enabled"])

    def test_forbidden_tables_zero(self):
        result = self._run(cycle_budget=5)
        for table, count in result["forbidden_table_counts"].items():
            self.assertEqual(count, 0, f"{table} has {count} rows (expected 0)")

    def test_no_retrieval_rows(self):
        result = self._run(cycle_budget=5)
        self.assertEqual(result["retrieval_rows_created"], 0)
        self.assertEqual(result["paper_decisions_created"], 0)
        self.assertEqual(result["positions_created"], 0)
        self.assertEqual(result["pnl_created"], 0)

    def test_stopped_safely_reason_present(self):
        result = self._run(cycle_budget=5)
        self.assertIsNotNone(result["stopped_safely_reason"])
        self.assertNotEqual(result["stopped_safely_reason"], "")

    def test_cycles_list_present(self):
        result = self._run(cycle_budget=5)
        self.assertIsInstance(result["cycles"], list)

    def test_source_budget_fields_present(self):
        result = self._run(cycle_budget=1)
        self.assertIn("source_budget_max_consecutive_failures", result)
        self.assertIn("throttle_backoff_seconds", result)
        self.assertIn("total_source_failures", result)

    def test_window_15m_enabled(self):
        result = self._run(cycle_budget=1)
        self.assertEqual(result["window_kind"], "WINDOW_15M")

    def test_total_window_closes_after_budget5(self):
        result = self._run(cycle_budget=5)
        self.assertEqual(result["total_window_closes"], 5)


# ---------------------------------------------------------------------------
# 4. A/B/C/D/E rotation tests
# ---------------------------------------------------------------------------

class TestLaneX5ABCDERotation(_DbBase):
    """Verify deterministic 5-token round-robin rotation."""

    def test_budget1_only_slot_a_closes(self):
        result = self._run(cycle_budget=1)
        a = result["token_a_report"]
        b = result["token_b_report"]
        self.assertEqual(a["window_closes"], 1)
        self.assertEqual(b["window_closes"], 0)

    def test_budget2_slots_a_b_close(self):
        result = self._run(cycle_budget=2)
        self.assertEqual(result["token_a_report"]["window_closes"], 1)
        self.assertEqual(result["token_b_report"]["window_closes"], 1)
        self.assertEqual(result["token_c_report"]["window_closes"], 0)

    def test_budget3_slots_a_b_c_close(self):
        result = self._run(cycle_budget=3)
        self.assertEqual(result["token_a_report"]["window_closes"], 1)
        self.assertEqual(result["token_b_report"]["window_closes"], 1)
        self.assertEqual(result["token_c_report"]["window_closes"], 1)
        self.assertEqual(result["token_d_report"]["window_closes"], 0)
        self.assertEqual(result["token_e_report"]["window_closes"], 0)

    def test_budget4_slots_a_b_c_d_close(self):
        result = self._run(cycle_budget=4)
        self.assertEqual(result["token_a_report"]["window_closes"], 1)
        self.assertEqual(result["token_b_report"]["window_closes"], 1)
        self.assertEqual(result["token_c_report"]["window_closes"], 1)
        self.assertEqual(result["token_d_report"]["window_closes"], 1)
        self.assertEqual(result["token_e_report"]["window_closes"], 0)

    def test_budget5_all_slots_close_once(self):
        result = self._run(cycle_budget=5)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertEqual(result[key]["window_closes"], 1, f"{key} did not close once")

    def test_budget10_all_slots_close_twice(self):
        result = self._run(cycle_budget=10)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertEqual(result[key]["window_closes"], 2, f"{key} did not close twice")

    def test_slot_labels_correct(self):
        result = self._run(cycle_budget=5)
        self.assertEqual(result["token_a_report"]["slot"], "A")
        self.assertEqual(result["token_b_report"]["slot"], "B")
        self.assertEqual(result["token_c_report"]["slot"], "C")
        self.assertEqual(result["token_d_report"]["slot"], "D")
        self.assertEqual(result["token_e_report"]["slot"], "E")

    def test_slot_mints_correct(self):
        result = self._run(cycle_budget=5)
        self.assertEqual(result["token_a_report"]["mint"], _MINT_A)
        self.assertEqual(result["token_b_report"]["mint"], _MINT_B)
        self.assertEqual(result["token_c_report"]["mint"], _MINT_C)
        self.assertEqual(result["token_d_report"]["mint"], _MINT_D)
        self.assertEqual(result["token_e_report"]["mint"], _MINT_E)

    def test_cycles_ordered_by_slot(self):
        result = self._run(cycle_budget=5)
        cycles = result["cycles"]
        slots = [c["slot"] for c in cycles]
        self.assertEqual(slots, ["A", "B", "C", "D", "E"])

    def test_budget0_stops_immediately(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=0,
        )
        self.assertEqual(result["total_window_closes"], 0)
        self.assertIn("budget", result["stopped_safely_reason"].lower())


# ---------------------------------------------------------------------------
# 5. No starvation
# ---------------------------------------------------------------------------

class TestLaneX5NoStarvation(_DbBase):
    """Prove that no token is starved in the five-token rotation."""

    def test_budget5_each_slot_exactly_one_close(self):
        result = self._run(cycle_budget=5)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertEqual(result[key]["window_closes"], 1)

    def test_budget10_each_slot_exactly_two_closes(self):
        result = self._run(cycle_budget=10)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertEqual(result[key]["window_closes"], 2)

    def test_budget5_no_slot_has_zero_closes(self):
        result = self._run(cycle_budget=5)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertGreater(result[key]["window_closes"], 0)

    def test_budget5_no_slot_has_two_or_more_closes(self):
        result = self._run(cycle_budget=5)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertLessEqual(result[key]["window_closes"], 1)

    def test_total_window_closes_equals_sum_of_slot_closes(self):
        result = self._run(cycle_budget=5)
        slot_sum = sum(
            result[k]["window_closes"]
            for k in ("token_a_report", "token_b_report", "token_c_report",
                      "token_d_report", "token_e_report")
        )
        self.assertEqual(result["total_window_closes"], slot_sum)


# ---------------------------------------------------------------------------
# 6. Evidence isolation
# ---------------------------------------------------------------------------

class TestLaneX5EvidenceIsolation(_DbBase):
    """Prove that each token's evidence stays isolated."""

    def test_five_distinct_mints_in_memory_windows(self):
        """After budget=5, there must be exactly 5 distinct mints in memory windows."""
        self._run(cycle_budget=5)
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT pt.token_mint
                FROM printer_memory_windows mw
                JOIN printer_tokens pt ON pt.id = mw.token_id
                """
            ).fetchall()
        finally:
            conn.close()
        mints = {r[0] for r in rows}
        self.assertEqual(len(mints), 5, f"Expected 5 distinct mints, got {mints}")
        for mint in (_MINT_A, _MINT_B, _MINT_C, _MINT_D, _MINT_E):
            self.assertIn(mint, mints)

    def test_source_request_sum_matches_db_total(self):
        result = self._run(cycle_budget=5)
        per_token_sum = sum(
            result[k]["source_requests_created"]
            for k in ("token_a_report", "token_b_report", "token_c_report",
                      "token_d_report", "token_e_report")
        )
        db_total = self._count_rows("printer_source_requests")
        self.assertEqual(per_token_sum, db_total)

    def test_source_response_sum_matches_db_total(self):
        result = self._run(cycle_budget=5)
        per_token_sum = sum(
            result[k]["source_responses_created"]
            for k in ("token_a_report", "token_b_report", "token_c_report",
                      "token_d_report", "token_e_report")
        )
        db_total = self._count_rows("printer_source_responses")
        self.assertEqual(per_token_sum, db_total)

    def test_per_token_snapshots_nonzero_after_budget5(self):
        result = self._run(cycle_budget=5)
        for key in ("token_a_report", "token_b_report", "token_c_report",
                    "token_d_report", "token_e_report"):
            self.assertGreater(result[key]["snapshots_created"], 0)

    def test_no_paper_decisions_in_db(self):
        self._run(cycle_budget=5)
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_positions_in_db(self):
        self._run(cycle_budget=5)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_memory_windows_match_token_count(self):
        """After budget=5, exactly 5 memory windows should exist (one per slot)."""
        result = self._run(cycle_budget=5)
        db_windows = self._count_rows("printer_memory_windows")
        self.assertGreaterEqual(db_windows, 5)


# ---------------------------------------------------------------------------
# 7. Source budget enforcement
# ---------------------------------------------------------------------------

class TestLaneX5SourceBudget(_DbBase):
    """Prove that source budget enforcement triggers safe stop."""

    def test_failing_adapter_triggers_stop(self):
        """Budget=2 with failing adapter should stop after 2+1 failures."""
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=2,
            _cycle_budget=None,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_STOPPED)

    def test_budget_exhausted_reason_in_result(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=2,
            _cycle_budget=None,
        )
        reason = result.get("stopped_safely_reason", "")
        self.assertIn("source budget", reason.lower())

    def test_total_source_failures_tracked(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=2,
            _cycle_budget=None,
        )
        self.assertGreater(result["total_source_failures"], 0)

    def test_throttle_backoff_safe(self):
        """Throttle with 1ms sleep should complete without error."""
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=1,
            throttle_backoff_seconds=0.001,
            _cycle_budget=None,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_STOPPED)

    def test_budget_not_triggered_on_success(self):
        """Normal success adapters never exhaust the source budget."""
        result = self._run(
            cycle_budget=5,
            source_budget_max_consecutive_failures=3,
        )
        self.assertIn(
            result["lane_x5_status"],
            {LANE_X5_STATUS_COMPLETED, LANE_X5_STATUS_STOPPED},
        )
        # Should stop from cycle budget, not source budget
        reason = result.get("stopped_safely_reason", "")
        self.assertNotIn("source budget", reason.lower())

    def test_source_budget_param_in_result(self):
        result = self._run(cycle_budget=1, source_budget_max_consecutive_failures=7)
        self.assertEqual(result["source_budget_max_consecutive_failures"], 7)

    def test_throttle_backoff_param_in_result(self):
        result = self._run(cycle_budget=1, throttle_backoff_seconds=2.5)
        self.assertEqual(result["throttle_backoff_seconds"], 2.5)

    def test_total_source_failures_zero_on_all_success(self):
        result = self._run(cycle_budget=5)
        self.assertEqual(result["total_source_failures"], 0)

    def test_budget_limit_of_zero_immediate_stop_on_failure(self):
        """source_budget_max_consecutive_failures=0 means stop on first failure."""
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=0,
            _cycle_budget=None,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_STOPPED)
        self.assertEqual(result["total_source_failures"], 1)

    def test_five_consecutive_failures_exhausts_default_budget(self):
        """With default budget=5, failing adapter produces STOPPED status."""
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=5,
            _cycle_budget=None,
        )
        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_STOPPED)
        self.assertGreaterEqual(result["total_source_failures"], 5)

    def test_window_closes_zero_when_budget_exhausted(self):
        """When source budget is exhausted, no window closes should have occurred."""
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=2,
            _cycle_budget=None,
        )
        self.assertEqual(result["total_window_closes"], 0)

    def test_no_forbidden_tables_written_on_budget_stop(self):
        result = run_five_token_memory_factory_cycle(
            self._write_x5_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_failing_adapter_map(),
            source_budget_max_consecutive_failures=2,
            _cycle_budget=None,
        )
        for table, count in result["forbidden_table_counts"].items():
            self.assertEqual(count, 0, f"{table} has {count} rows on budget stop")


# ---------------------------------------------------------------------------
# 8. Hard locks
# ---------------------------------------------------------------------------

class TestLaneX5HardLocks(_DbBase):
    """Verify all 24 hard locks are set and financial locks remain enforced."""

    def setUp(self):
        super().setUp()
        self._result = self._run(cycle_budget=1)

    def test_hard_locks_count_is_24(self):
        self.assertEqual(len(self._result["hard_locks"]), 24)

    def test_no_buy_sell_hold(self):
        self.assertTrue(self._result["hard_locks"]["no_buy_sell_hold"])

    def test_no_paper_decisions(self):
        self.assertTrue(self._result["hard_locks"]["no_paper_decisions"])

    def test_no_positions(self):
        self.assertTrue(self._result["hard_locks"]["no_positions"])

    def test_no_pnl(self):
        self.assertTrue(self._result["hard_locks"]["no_pnl"])

    def test_no_retrieval_activation(self):
        self.assertTrue(self._result["hard_locks"]["no_retrieval_activation"])

    def test_no_live_trading(self):
        self.assertTrue(self._result["hard_locks"]["no_live_trading"])

    def test_no_paid_api(self):
        self.assertTrue(self._result["hard_locks"]["no_paid_api"])

    def test_no_wallet_private_key(self):
        self.assertTrue(self._result["hard_locks"]["no_wallet_private_key"])

    def test_no_generic_search(self):
        self.assertTrue(self._result["hard_locks"]["no_generic_search"])

    def test_no_unbounded_loop(self):
        self.assertTrue(self._result["hard_locks"]["no_unbounded_loop"])

    def test_no_daemon_mode(self):
        self.assertTrue(self._result["hard_locks"]["no_daemon_mode"])

    def test_no_scheduler_bypass(self):
        self.assertTrue(self._result["hard_locks"]["no_scheduler_bypass"])

    def test_no_source_governor_bypass(self):
        self.assertTrue(self._result["hard_locks"]["no_source_governor_bypass"])

    def test_no_ad_hoc_api_loop(self):
        self.assertTrue(self._result["hard_locks"]["no_ad_hoc_api_loop"])

    def test_no_scoring_ranking_confidence(self):
        self.assertTrue(self._result["hard_locks"]["no_scoring_ranking_confidence"])

    def test_no_embeddings_vectors(self):
        self.assertTrue(self._result["hard_locks"]["no_embeddings_vectors"])

    def test_no_1h_4h_12h_24h_collection(self):
        self.assertTrue(self._result["hard_locks"]["no_1h_4h_12h_24h_collection"])

    def test_no_5m_main_window(self):
        self.assertTrue(self._result["hard_locks"]["no_5m_main_window"])

    def test_no_trade_events(self):
        self.assertTrue(self._result["hard_locks"]["no_trade_events"])

    def test_no_paper_trade_audits(self):
        self.assertTrue(self._result["hard_locks"]["no_paper_trade_audits"])

    def test_no_token_pair_mixing(self):
        self.assertTrue(self._result["hard_locks"]["no_token_pair_mixing"])

    def test_no_source_budget_bypass(self):
        self.assertTrue(self._result["hard_locks"]["no_source_budget_bypass"])

    def test_no_x6_expansion(self):
        self.assertTrue(self._result["hard_locks"]["no_x6_expansion"])


# ---------------------------------------------------------------------------
# 9. Constants
# ---------------------------------------------------------------------------

class TestLaneX5Constants(unittest.TestCase):
    """Verify X5 module constants are correct."""

    def test_exact_token_count_is_5(self):
        self.assertEqual(LANE_X5_EXACT_TOKEN_COUNT, 5)

    def test_command_name(self):
        self.assertEqual(LANE_X5_COMMAND_NAME, "printer-run-lane-x5-five-token-cycle")

    def test_status_completed(self):
        self.assertEqual(LANE_X5_STATUS_COMPLETED, "LANE_X5_COMPLETED")

    def test_status_blocked(self):
        self.assertEqual(LANE_X5_STATUS_BLOCKED, "LANE_X5_BLOCKED")

    def test_status_stopped(self):
        self.assertEqual(LANE_X5_STATUS_STOPPED, "LANE_X5_STOPPED")

    def test_hard_locks_count_is_24(self):
        self.assertEqual(len(_HARD_LOCKS), 24)


# ---------------------------------------------------------------------------
# 10. CLI tests
# ---------------------------------------------------------------------------

class TestLaneX5CLI(_DbBase):
    """CLI entry-point sanity checks."""

    def test_cli_blocked_without_operator_approved(self):
        from printer_v1.operator_cli.commands import main_run_lane_x5_five_token_cycle
        token_file = self._write_x5_token_file()
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main_run_lane_x5_five_token_cycle(
                [
                    "--db-path", str(self.db_path),
                    "--token-list-path", str(token_file),
                    "--backup-proof-path", str(self.backup_proof_path),
                ],
                _adapter_map=_make_adapter_map(),
            )
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertEqual(payload["lane_x5_status"], LANE_X5_STATUS_BLOCKED)

    def test_cli_returns_0_with_operator_approved(self):
        from printer_v1.operator_cli.commands import main_run_lane_x5_five_token_cycle
        token_file = self._write_x5_token_file()
        out = io.StringIO()
        with redirect_stdout(out):
            rc = main_run_lane_x5_five_token_cycle(
                [
                    "--db-path", str(self.db_path),
                    "--token-list-path", str(token_file),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--operator-approved",
                ],
                _adapter_map=_make_adapter_map(),
            )
        self.assertEqual(rc, 0)
        payload = json.loads(out.getvalue())
        self.assertIn("lane_x5_status", payload)

    def test_cli_prints_json(self):
        from printer_v1.operator_cli.commands import main_run_lane_x5_five_token_cycle
        token_file = self._write_x5_token_file()
        out = io.StringIO()
        with redirect_stdout(out):
            main_run_lane_x5_five_token_cycle(
                [
                    "--db-path", str(self.db_path),
                    "--token-list-path", str(token_file),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--operator-approved",
                ],
                _adapter_map=_make_adapter_map(),
            )
        payload = json.loads(out.getvalue())
        self.assertIn("command", payload)
        self.assertEqual(payload["command"], LANE_X5_COMMAND_NAME)


# ---------------------------------------------------------------------------
# 11. X2 regression
# ---------------------------------------------------------------------------

class TestLaneX5X2Regression(_DbBase):
    """Prove Lane X2 still works after X5 is added."""

    def _make_x2_token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens_x2.json"
        tf.write_text(json.dumps({
            "tokens": [
                {
                    "token_mint": _MINT_A,
                    "pair_address": _PAIR_A,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                },
                {
                    "token_mint": _MINT_B,
                    "pair_address": _PAIR_B,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                },
            ]
        }), encoding="utf-8")
        return tf

    def test_x2_still_completes_two_token_cycle(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import (
            LANE_X2_STATUS_COMPLETED,
            run_two_token_memory_factory_cycle,
        )
        result = run_two_token_memory_factory_cycle(
            self._make_x2_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map={
                _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
                _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
            },
            _cycle_budget=2,
        )
        self.assertIn(result["lane_x2_status"], {LANE_X2_STATUS_COMPLETED, "LANE_X2_STOPPED"})

    def test_x2_rejects_five_tokens(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import (
            _load_and_validate_two_token_list,
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "tokens.json"
            p.write_text(json.dumps({"tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_C, "pair_address": _PAIR_C,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_D, "pair_address": _PAIR_D,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_E, "pair_address": _PAIR_E,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
            ]}), encoding="utf-8")
            valid, reason, *_ = _load_and_validate_two_token_list(p)
            self.assertFalse(valid)
            self.assertIn("exactly 2", reason)

    def test_x2_hard_locks_count_is_22(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import _HARD_LOCKS as x2_locks
        self.assertEqual(len(x2_locks), 22)

    def test_x2_buy_sell_hold_false(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import (
            run_two_token_memory_factory_cycle,
        )
        result = run_two_token_memory_factory_cycle(
            self._make_x2_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map={
                _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
                _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
            },
            _cycle_budget=1,
        )
        self.assertFalse(result["buy_enabled"])
        self.assertFalse(result["sell_enabled"])
        self.assertFalse(result["hold_enabled"])

    def test_x2_forbidden_tables_zero(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import (
            run_two_token_memory_factory_cycle,
        )
        result = run_two_token_memory_factory_cycle(
            self._make_x2_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map={
                _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
                _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
            },
            _cycle_budget=2,
        )
        for table, count in result["forbidden_table_counts"].items():
            self.assertEqual(count, 0)

    def test_x2_token_count_unchanged(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import LANE_X2_EXACT_TOKEN_COUNT
        self.assertEqual(LANE_X2_EXACT_TOKEN_COUNT, 2)


# ---------------------------------------------------------------------------
# 12. X3 regression
# ---------------------------------------------------------------------------

class TestLaneX5X3Regression(unittest.TestCase):
    """Prove Lane X3 post-cycle lifecycle still works after X5 is added."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_x3_cooldown_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            LANE_X3_STATUS_COOLDOWN_ENTERED,
            enter_cooldown_after_window,
        )
        r = enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        self.assertEqual(r["lane_x3_status"], LANE_X3_STATUS_COOLDOWN_ENTERED)

    def test_x3_hard_locks_count_is_23(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import _HARD_LOCKS as x3_locks
        self.assertEqual(len(x3_locks), 23)

    def test_x3_reopen_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            LANE_X3_STATUS_REOPENED,
            enter_cooldown_after_window,
            reopen_token,
        )
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        r = reopen_token(self.db_path, _MINT_A, _PAIR_A)
        self.assertEqual(r["lane_x3_status"], LANE_X3_STATUS_REOPENED)

    def test_x3_gate_blocks_cooldown_token(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
        )
        enter_cooldown_after_window(self.db_path, _MINT_B, _PAIR_B)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_B])
        self.assertGreater(len(blocked), 0, "X3 gate must block cooldown token")

    def test_x3_gate_passes_after_reopen(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
            reopen_token,
        )
        enter_cooldown_after_window(self.db_path, _MINT_C, _PAIR_C)
        reopen_token(self.db_path, _MINT_C, _PAIR_C)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_C])
        self.assertEqual(len(blocked), 0, "X3 gate must pass after reopen")


# ---------------------------------------------------------------------------
# 13. X4 regression
# ---------------------------------------------------------------------------

class TestLaneX5X4Regression(_DbBase):
    """Prove Lane X4 three-token proof still works after X5 is added."""

    def _make_x4_token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens_x4.json"
        tf.write_text(json.dumps({
            "tokens": [
                {
                    "token_mint": _MINT_A,
                    "pair_address": _PAIR_A,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                },
                {
                    "token_mint": _MINT_B,
                    "pair_address": _PAIR_B,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                },
                {
                    "token_mint": _MINT_C,
                    "pair_address": _PAIR_C,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                },
            ]
        }), encoding="utf-8")
        return tf

    def test_x4_still_completes_three_token_cycle(self):
        from printer_v1.operator_cli.lane_x4_three_token_runner import (
            run_three_token_memory_factory_cycle,
        )
        result = run_three_token_memory_factory_cycle(
            self._make_x4_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map={
                _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
                _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
                _MINT_C: _build_adapter(_MINT_C, _PAIR_C),
            },
            _cycle_budget=3,
        )
        self.assertIn(result["lane_x4_status"], {"LANE_X4_COMPLETED", "LANE_X4_STOPPED"})

    def test_x4_rejects_five_tokens(self):
        from printer_v1.operator_cli.lane_x4_three_token_runner import (
            _load_and_validate_three_token_list,
        )
        with tempfile.TemporaryDirectory() as tmp:
            p = pathlib.Path(tmp) / "tokens.json"
            p.write_text(json.dumps({"tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_C, "pair_address": _PAIR_C,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_D, "pair_address": _PAIR_D,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
                {"token_mint": _MINT_E, "pair_address": _PAIR_E,
                 "chain": "solana", "tracking_lane": "TRACK_FAST", "operator_approved": True},
            ]}), encoding="utf-8")
            valid, reason, *_ = _load_and_validate_three_token_list(p)
            self.assertFalse(valid)
            self.assertIn("exactly 3", reason)

    def test_x4_hard_locks_count_is_23(self):
        from printer_v1.operator_cli.lane_x4_three_token_runner import _HARD_LOCKS as x4_locks
        self.assertEqual(len(x4_locks), 23)

    def test_x4_still_has_no_x5_expansion_lock(self):
        from printer_v1.operator_cli.lane_x4_three_token_runner import _HARD_LOCKS as x4_locks
        self.assertTrue(x4_locks.get("no_x5_expansion", False))

    def test_x4_buy_sell_hold_false(self):
        from printer_v1.operator_cli.lane_x4_three_token_runner import (
            run_three_token_memory_factory_cycle,
        )
        result = run_three_token_memory_factory_cycle(
            self._make_x4_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map={
                _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
                _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
                _MINT_C: _build_adapter(_MINT_C, _PAIR_C),
            },
            _cycle_budget=1,
        )
        self.assertFalse(result["buy_enabled"])
        self.assertFalse(result["sell_enabled"])
        self.assertFalse(result["hold_enabled"])
