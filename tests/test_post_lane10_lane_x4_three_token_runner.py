"""Lane X4 — Three-Token Controlled 15m Proof tests.

Validates:
- Exactly 3 TRACK_FAST operator-approved Solana tokens accepted; 1/2/4/0/duplicates rejected.
- Unapproved, non-TRACK_FAST, non-solana, placeholder tokens rejected.
- A/B/C deterministic rotation: ticks 0→A, 1→B, 2→C, 3→A, ...
- No token starvation: budget=3 gives each slot exactly 1 window close.
- Evidence isolated per token — token A snapshots cannot build token B/C memory.
- Per-token source/snapshot/window-close counts reported independently.
- All retrieval/paper/BUY/position/PnL locks remain zero.
- Hard locks dict: 23 keys all True (includes no_x5_expansion).
- Idempotent Lane K replay: second call creates zero new rows.
- All window-kind gates remain: 5m forbidden as main, 1h/4h/12h/24h blocked.
- Zero clean memories is a valid outcome.
- X2 (79 tests) and X3 (97 tests) regression — neither module is modified.
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
from printer_v1.operator_cli.lane_x4_three_token_runner import (
    LANE_X4_COMMAND_NAME,
    LANE_X4_EXACT_TOKEN_COUNT,
    LANE_X4_STATUS_BLOCKED,
    LANE_X4_STATUS_COMPLETED,
    LANE_X4_STATUS_STOPPED,
    _HARD_LOCKS,
    _load_and_validate_three_token_list,
    run_three_token_memory_factory_cycle,
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

_PAIR_A = "LaneX4TestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_B = "LaneX4TestPairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_PAIR_C = "LaneX4TestPairCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"

_MINT_EXTRA = "6zPGm6QT7U5jlhPbE9ClNs46xjNFck6tsxPbN3sWFpump"

_REQUIRED_REPORTING_FIELDS = frozenset({
    "command",
    "lane_x4_status",
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
    "hard_locks",
    "buy_enabled",
    "sell_enabled",
    "hold_enabled",
    "token_a_report",
    "token_b_report",
    "token_c_report",
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
                    "symbol": "X4T",
                    "name": "Lane X4 Test Token",
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


def _make_adapter_map():
    return {
        _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
        _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
        _MINT_C: _build_adapter(_MINT_C, _PAIR_C),
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

    def _write_x4_token_file(
        self,
        *,
        mint_a: str = _MINT_A,
        pair_a: str = _PAIR_A,
        mint_b: str = _MINT_B,
        pair_b: str = _PAIR_B,
        mint_c: str = _MINT_C,
        pair_c: str = _PAIR_C,
        tracking_lane_a: str = "TRACK_FAST",
        tracking_lane_b: str = "TRACK_FAST",
        tracking_lane_c: str = "TRACK_FAST",
        approved_a: bool = True,
        approved_b: bool = True,
        approved_c: bool = True,
        tokens_override: list | None = None,
    ) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens_x4.json"
        if tokens_override is not None:
            data = {"tokens": tokens_override}
        else:
            data = {
                "tokens": [
                    {
                        "token_mint": mint_a,
                        "pair_address": pair_a,
                        "chain": "solana",
                        "tracking_lane": tracking_lane_a,
                        "operator_approved": approved_a,
                    },
                    {
                        "token_mint": mint_b,
                        "pair_address": pair_b,
                        "chain": "solana",
                        "tracking_lane": tracking_lane_b,
                        "operator_approved": approved_b,
                    },
                    {
                        "token_mint": mint_c,
                        "pair_address": pair_c,
                        "chain": "solana",
                        "tracking_lane": tracking_lane_c,
                        "operator_approved": approved_c,
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
        token_file = self._write_x4_token_file()
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
        return run_three_token_memory_factory_cycle(**defaults)


# ---------------------------------------------------------------------------
# 1. Validator tests — no DB
# ---------------------------------------------------------------------------

class TestLaneX4ThreeTokenValidator(unittest.TestCase):
    """Unit tests for _load_and_validate_three_token_list."""

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

    def test_three_tokens_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, tok_a, tok_b, tok_c = _load_and_validate_three_token_list(path)
            self.assertTrue(valid, reason)
            self.assertEqual(tok_a["token_mint"], _MINT_A)
            self.assertEqual(tok_b["token_mint"], _MINT_B)
            self.assertEqual(tok_c["token_mint"], _MINT_C)

    def test_one_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([self._valid_token(_MINT_A, _PAIR_A)], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("3", reason)
            self.assertIn("1", reason)

    def test_two_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("2", reason)

    def test_four_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
                self._valid_token(_MINT_EXTRA, "PAIR_X4"),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("4", reason)

    def test_zero_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("0", reason)

    def test_unapproved_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tok = self._valid_token(_MINT_C, _PAIR_C)
            tok["operator_approved"] = False
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                tok,
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("operator_approved", reason)

    def test_track_normal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tok = self._valid_token(_MINT_A, _PAIR_A)
            tok["tracking_lane"] = "TRACK_NORMAL"
            path = self._write([
                tok,
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("TRACK_FAST", reason)

    def test_watch_only_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tok = self._valid_token(_MINT_B, _PAIR_B)
            tok["tracking_lane"] = "WATCH_ONLY"
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                tok,
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)

    def test_non_solana_chain_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tok = self._valid_token(_MINT_A, _PAIR_A)
            tok["chain"] = "ethereum"
            path = self._write([
                tok,
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("solana", reason)

    def test_placeholder_mint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tok = self._valid_token("PLACEHOLDER_MINT_C", _PAIR_C)
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                tok,
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("placeholder", reason.lower())

    def test_placeholder_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tok = self._valid_token(_MINT_A, "PLACEHOLDER_PAIR_A")
            path = self._write([
                tok,
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("placeholder", reason.lower())

    def test_empty_mint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tok = self._valid_token("", _PAIR_A)
            path = self._write([
                tok,
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)

    def test_duplicate_mints_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
                self._valid_token(_MINT_A, _PAIR_C),  # duplicate mint
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("duplicate", reason.lower())
            self.assertIn("mint", reason.lower())

    def test_duplicate_pair_addresses_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_A),  # duplicate pair
                self._valid_token(_MINT_C, _PAIR_C),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid)
            self.assertIn("duplicate", reason.lower())
            self.assertIn("pair", reason.lower())

    def test_missing_file_rejected(self):
        valid, reason, _, _, _ = _load_and_validate_three_token_list(
            "/nonexistent/path/tokens.json"
        )
        self.assertFalse(valid)
        self.assertIn("not found", reason.lower())

    def test_none_path_rejected(self):
        valid, reason, _, _, _ = _load_and_validate_three_token_list(None)
        self.assertFalse(valid)
        self.assertIn("required", reason.lower())

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = pathlib.Path(tmp) / "bad.json"
            bad.write_text("NOT_JSON", encoding="utf-8")
            valid, reason, _, _, _ = _load_and_validate_three_token_list(bad)
            self.assertFalse(valid)
            self.assertIn("unreadable", reason.lower())

    def test_x2_format_two_tokens_rejected_by_x4_validator(self):
        """An X2 token list (2 tokens) must be rejected by the X4 validator."""
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                self._valid_token(_MINT_A, _PAIR_A),
                self._valid_token(_MINT_B, _PAIR_B),
            ], tmp)
            valid, reason, _, _, _ = _load_and_validate_three_token_list(path)
            self.assertFalse(valid, "X2 two-token list must be rejected by X4 validator")


# ---------------------------------------------------------------------------
# 2. Gate / blocked tests
# ---------------------------------------------------------------------------

class TestLaneX4GateChecks(_DbBase):
    """run_three_token_memory_factory_cycle must return LANE_X4_BLOCKED for bad inputs."""

    def test_blocked_without_operator_approved(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)
        self.assertIn("operator_approved", str(r.get("blocked_reasons", "")))

    def test_blocked_missing_token_list_path(self):
        r = run_three_token_memory_factory_cycle(
            None, self.db_path, self.backup_proof_path,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_nonexistent_token_list_path(self):
        r = run_three_token_memory_factory_cycle(
            "/nonexistent/tokens.json", self.db_path, self.backup_proof_path,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_missing_db_path(self):
        r = run_three_token_memory_factory_cycle(
            self._write_x4_token_file(), None, self.backup_proof_path,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_missing_backup_proof_path(self):
        r = run_three_token_memory_factory_cycle(
            self._write_x4_token_file(), self.db_path, None,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_window_5m_as_main(self):
        r = self._run(window_kind="WINDOW_5M_MICRO_EVENT")
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_window_1h_as_main(self):
        r = self._run(window_kind="WINDOW_1H")
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_window_4h_as_main(self):
        r = self._run(window_kind="WINDOW_4H")
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_window_12h_as_main(self):
        r = self._run(window_kind="WINDOW_12H")
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_window_24h_as_main(self):
        r = self._run(window_kind="WINDOW_24H")
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_12h_profile_without_allow_long_run(self):
        r = self._run(duration_profile="12h", allow_long_bounded_run=False)
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_24h_profile_without_allow_long_run(self):
        r = self._run(duration_profile="24h", allow_long_bounded_run=False)
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_one_token_in_list(self):
        token_file = pathlib.Path(self._tmp.name) / "one_token.json"
        token_file.write_text(json.dumps({
            "tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ]
        }), encoding="utf-8")
        r = run_three_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True, _adapter_map=_make_adapter_map(), _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_two_tokens_in_list(self):
        """X2-style two-token list must be rejected by the X4 runner."""
        token_file = pathlib.Path(self._tmp.name) / "two_tokens.json"
        token_file.write_text(json.dumps({
            "tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ]
        }), encoding="utf-8")
        r = run_three_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True, _adapter_map=_make_adapter_map(), _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_four_tokens_in_list(self):
        token_file = pathlib.Path(self._tmp.name) / "four_tokens.json"
        token_file.write_text(json.dumps({
            "tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_C, "pair_address": _PAIR_C,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_EXTRA, "pair_address": "PAIR_EXTRA",
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ]
        }), encoding="utf-8")
        r = run_three_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True, _adapter_map=_make_adapter_map(), _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_unapproved_token_in_list(self):
        token_file = self._write_x4_token_file(approved_c=False)
        r = run_three_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True, _adapter_map=_make_adapter_map(), _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_duplicate_mints_in_list(self):
        token_file = self._write_x4_token_file(mint_c=_MINT_A)
        r = run_three_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True, _adapter_map=_make_adapter_map(), _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_non_track_fast_in_list(self):
        token_file = self._write_x4_token_file(tracking_lane_b="TRACK_NORMAL")
        r = run_three_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True, _adapter_map=_make_adapter_map(), _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_blocked_placeholder_mint_in_list(self):
        token_file = self._write_x4_token_file(mint_a="PLACEHOLDER_MINT_A")
        r = run_three_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True, _adapter_map=_make_adapter_map(), _cycle_budget=1,
        )
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 3. Execution tests — happy-path
# ---------------------------------------------------------------------------

class TestLaneX4Execution(_DbBase):
    """End-to-end execution tests for the Lane X4 three-token runner."""

    def test_single_cycle_budget_completes(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["lane_x4_status"], LANE_X4_STATUS_COMPLETED)

    def test_selected_token_count_is_3(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["selected_token_count"], LANE_X4_EXACT_TOKEN_COUNT)

    def test_token_a_mint_in_result(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["token_a_mint"], _MINT_A)

    def test_token_b_mint_in_result(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["token_b_mint"], _MINT_B)

    def test_token_c_mint_in_result(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["token_c_mint"], _MINT_C)

    def test_required_reporting_fields_present(self):
        r = self._run(cycle_budget=1)
        missing = _REQUIRED_REPORTING_FIELDS - r.keys()
        self.assertFalse(missing, f"Missing fields: {missing}")

    def test_token_a_report_present_and_has_required_fields(self):
        r = self._run(cycle_budget=1)
        rep = r.get("token_a_report")
        self.assertIsNotNone(rep, "token_a_report must be present")
        missing = _TOKEN_REPORT_FIELDS - rep.keys()
        self.assertFalse(missing, f"Missing token_a_report fields: {missing}")
        self.assertEqual(rep["slot"], "A")
        self.assertEqual(rep["mint"], _MINT_A)

    def test_token_b_report_present_and_has_required_fields(self):
        r = self._run(cycle_budget=1)
        rep = r.get("token_b_report")
        self.assertIsNotNone(rep, "token_b_report must be present")
        missing = _TOKEN_REPORT_FIELDS - rep.keys()
        self.assertFalse(missing, f"Missing token_b_report fields: {missing}")
        self.assertEqual(rep["slot"], "B")
        self.assertEqual(rep["mint"], _MINT_B)

    def test_token_c_report_present_and_has_required_fields(self):
        r = self._run(cycle_budget=3)
        rep = r.get("token_c_report")
        self.assertIsNotNone(rep, "token_c_report must be present")
        missing = _TOKEN_REPORT_FIELDS - rep.keys()
        self.assertFalse(missing, f"Missing token_c_report fields: {missing}")
        self.assertEqual(rep["slot"], "C")
        self.assertEqual(rep["mint"], _MINT_C)

    def test_window_kind_enabled_15m(self):
        r = self._run(cycle_budget=1)
        self.assertTrue(r["window_kind_enabled"])
        self.assertEqual(r["window_kind"], "WINDOW_15M")

    def test_disabled_collection_window_kinds_reported(self):
        r = self._run(cycle_budget=1)
        disabled = set(r.get("disabled_collection_window_kinds", []))
        self.assertIn("WINDOW_1H", disabled)
        self.assertIn("WINDOW_4H", disabled)
        self.assertIn("WINDOW_12H", disabled)
        self.assertIn("WINDOW_24H", disabled)

    def test_support_only_window_kinds_reported(self):
        r = self._run(cycle_budget=1)
        support_only = set(r.get("support_only_window_kinds", []))
        self.assertIn("WINDOW_5M_MICRO_EVENT", support_only)

    def test_zero_clean_memories_is_valid(self):
        r = self._run(cycle_budget=1)
        self.assertTrue(r["zero_clean_memories_is_valid"])
        self.assertGreaterEqual(r["clean_memory_rows_created"], 0)

    def test_stopped_safely_reason_present(self):
        r = self._run(cycle_budget=1)
        self.assertIsNotNone(r.get("stopped_safely_reason"))
        self.assertGreater(len(r["stopped_safely_reason"]), 0)

    def test_operator_approved_in_result(self):
        r = self._run(cycle_budget=1)
        self.assertTrue(r["operator_approved"])

    def test_db_path_in_result(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["db_path"], str(self.db_path))

    def test_second_cycle_run_does_not_error(self):
        """Running the three-token cycle twice must not raise or return BLOCKED."""
        r1 = self._run(cycle_budget=1)
        r2 = self._run(cycle_budget=1)
        self.assertEqual(r1["lane_x4_status"], LANE_X4_STATUS_COMPLETED)
        self.assertEqual(r2["lane_x4_status"], LANE_X4_STATUS_COMPLETED)

    def test_no_running_jobs_after_cycle(self):
        """Scheduler jobs must not be left RUNNING after the cycle exits."""
        self._run(cycle_budget=3)
        running = self._count_rows_where("printer_scheduler_jobs", "status = 'RUNNING'")
        self.assertEqual(running, 0, "No RUNNING scheduler jobs must remain after cycle")

    def test_idempotent_lane_k_replay(self):
        """After running the cycle, a second Lane K call must create zero new rows."""
        self._run(cycle_budget=3)
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
        k1 = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertIn("clean_memory_rows_created", k1)
        k2 = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(
            k2["clean_memory_rows_created"], 0,
            "Second Lane K run must not create new clean-memory rows (idempotent)",
        )


# ---------------------------------------------------------------------------
# 4. A/B/C rotation tests
# ---------------------------------------------------------------------------

class TestLaneX4ABCRotation(_DbBase):
    """Deterministic A/B/C round-robin rotation proof."""

    def test_budget_1_only_slot_a_closes(self):
        """With budget=1, the only window close must be for slot A (first tick)."""
        r = self._run(cycle_budget=1)
        self.assertEqual(r["token_a_report"]["window_closes"], 1)
        self.assertEqual(r["token_b_report"]["window_closes"], 0)
        self.assertEqual(r["token_c_report"]["window_closes"], 0)

    def test_budget_1_total_closes_is_1(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["total_window_closes"], 1)

    def test_budget_2_slot_a_and_b_close(self):
        """With budget=2, A gets 1 close and B gets 1 close; C gets 0."""
        r = self._run(cycle_budget=2)
        self.assertEqual(r["token_a_report"]["window_closes"], 1)
        self.assertEqual(r["token_b_report"]["window_closes"], 1)
        self.assertEqual(r["token_c_report"]["window_closes"], 0)

    def test_budget_3_all_three_slots_get_one_close(self):
        """With budget=3, each slot gets exactly 1 window close — the ABC rotation proof."""
        r = self._run(cycle_budget=3)
        self.assertEqual(r["token_a_report"]["window_closes"], 1)
        self.assertEqual(r["token_b_report"]["window_closes"], 1)
        self.assertEqual(r["token_c_report"]["window_closes"], 1)

    def test_budget_3_total_closes_is_3(self):
        r = self._run(cycle_budget=3)
        self.assertEqual(r["total_window_closes"], 3)

    def test_budget_6_each_slot_gets_two_closes(self):
        """With budget=6, each slot gets exactly 2 window closes."""
        r = self._run(cycle_budget=6)
        self.assertEqual(r["token_a_report"]["window_closes"], 2)
        self.assertEqual(r["token_b_report"]["window_closes"], 2)
        self.assertEqual(r["token_c_report"]["window_closes"], 2)

    def test_budget_6_total_closes_is_6(self):
        r = self._run(cycle_budget=6)
        self.assertEqual(r["total_window_closes"], 6)

    def test_slot_window_closes_sum_to_total(self):
        r = self._run(cycle_budget=3)
        a = r["token_a_report"]["window_closes"]
        b = r["token_b_report"]["window_closes"]
        c = r["token_c_report"]["window_closes"]
        self.assertEqual(a + b + c, r["total_window_closes"])

    def test_cycles_list_slot_order_with_budget_3(self):
        """cycles list = A_cycles + B_cycles + C_cycles (concatenation, not temporal).
        With budget=3, each slot has 1 cycle, so index 0=A, 1=B, 2=C."""
        r = self._run(cycle_budget=3)
        cycles = r.get("cycles", [])
        self.assertEqual(len(cycles), 3)
        self.assertEqual(cycles[0]["slot"], "A")
        self.assertEqual(cycles[1]["slot"], "B")
        self.assertEqual(cycles[2]["slot"], "C")

    def test_cycles_list_carries_correct_mints(self):
        """Each cycle entry must carry the correct mint for its slot."""
        r = self._run(cycle_budget=3)
        for cyc in r.get("cycles", []):
            if cyc.get("slot") == "A":
                self.assertEqual(cyc.get("mint"), _MINT_A)
            elif cyc.get("slot") == "B":
                self.assertEqual(cyc.get("mint"), _MINT_B)
            elif cyc.get("slot") == "C":
                self.assertEqual(cyc.get("mint"), _MINT_C)


# ---------------------------------------------------------------------------
# 5. No-starvation proof
# ---------------------------------------------------------------------------

class TestLaneX4NoStarvation(_DbBase):
    """Proves that no token is systematically excluded from window closes."""

    def test_slot_c_gets_at_least_one_close_with_budget_3(self):
        """Slot C must get at least 1 window close when budget >= 3."""
        r = self._run(cycle_budget=3)
        self.assertGreaterEqual(
            r["token_c_report"]["window_closes"], 1,
            "Slot C must not be starved with budget=3",
        )

    def test_slot_c_gets_zero_closes_with_budget_2(self):
        """With budget=2, slot C has not been reached yet — window_closes must be 0."""
        r = self._run(cycle_budget=2)
        self.assertEqual(
            r["token_c_report"]["window_closes"], 0,
            "Slot C must have 0 closes with budget=2 (rotation: A→B→C, budget stops at B)",
        )

    def test_equal_distribution_budget_3(self):
        """All three slots get the same number of closes with budget=3 (k=3 → 1 each)."""
        r = self._run(cycle_budget=3)
        a = r["token_a_report"]["window_closes"]
        b = r["token_b_report"]["window_closes"]
        c = r["token_c_report"]["window_closes"]
        self.assertEqual(a, b, "Slots A and B must have equal closes")
        self.assertEqual(b, c, "Slots B and C must have equal closes")

    def test_equal_distribution_budget_6(self):
        """With budget=6, all three slots get exactly 2 closes."""
        r = self._run(cycle_budget=6)
        a = r["token_a_report"]["window_closes"]
        b = r["token_b_report"]["window_closes"]
        c = r["token_c_report"]["window_closes"]
        self.assertEqual(a, 2)
        self.assertEqual(b, 2)
        self.assertEqual(c, 2)

    def test_no_starvation_all_three_positive_with_budget_3(self):
        """All three per-token reports must show window_closes > 0 with budget=3."""
        r = self._run(cycle_budget=3)
        for slot, key in [("A", "token_a_report"), ("B", "token_b_report"), ("C", "token_c_report")]:
            closes = r[key]["window_closes"]
            self.assertGreater(closes, 0, f"Slot {slot} must not be starved (closes={closes})")


# ---------------------------------------------------------------------------
# 6. Evidence isolation tests
# ---------------------------------------------------------------------------

class TestLaneX4EvidenceIsolation(_DbBase):
    """Proves separate evidence identity per token — no mixing."""

    def test_slot_b_has_no_memory_windows_when_only_a_ran(self):
        """With budget=1, only slot A closes; token B must have 0 memory windows."""
        r = self._run(cycle_budget=1)
        self.assertEqual(
            r["token_b_report"]["memory_windows_created"], 0,
            "Token B must not have memory windows when only slot A ran",
        )

    def test_slot_c_has_no_memory_windows_when_only_a_ran(self):
        """With budget=1, slot C must have 0 memory windows."""
        r = self._run(cycle_budget=1)
        self.assertEqual(
            r["token_c_report"]["memory_windows_created"], 0,
            "Token C must not have memory windows when only slot A ran",
        )

    def test_each_slot_has_exactly_one_window_close_with_budget_3(self):
        """Verifies per-token isolation: each slot has window_closes == 1."""
        r = self._run(cycle_budget=3)
        self.assertEqual(r["token_a_report"]["window_closes"], 1)
        self.assertEqual(r["token_b_report"]["window_closes"], 1)
        self.assertEqual(r["token_c_report"]["window_closes"], 1)

    def test_per_token_source_counts_positive_with_budget_3(self):
        """After budget=3 execution, all per-token source request counts are > 0."""
        r = self._run(cycle_budget=3)
        for slot, key in [("A", "token_a_report"), ("B", "token_b_report"), ("C", "token_c_report")]:
            reqs = r[key]["source_requests_created"]
            self.assertGreater(reqs, 0, f"Token {slot} must have > 0 source requests")

    def test_per_token_source_counts_sum_to_db_total(self):
        """Sum of per-token source_requests must equal the DB total — no mixing."""
        r = self._run(cycle_budget=3)
        a_reqs = r["token_a_report"]["source_requests_created"]
        b_reqs = r["token_b_report"]["source_requests_created"]
        c_reqs = r["token_c_report"]["source_requests_created"]
        db_total = self._count_rows("printer_source_requests")
        self.assertEqual(
            a_reqs + b_reqs + c_reqs, db_total,
            f"Sum ({a_reqs}+{b_reqs}+{c_reqs}={a_reqs+b_reqs+c_reqs})"
            f" must equal DB total ({db_total})",
        )

    def test_mixed_token_memory_impossible(self):
        """Each memory window must be linked to exactly one token_mint.
        After budget=3, we have 3 windows — verify each belongs to a distinct mint."""
        self._run(cycle_budget=3)
        conn = sqlite3.connect(str(self.db_path))
        try:
            rows = conn.execute(
                """
                SELECT DISTINCT pt.token_mint
                FROM printer_memory_windows mw
                JOIN printer_tokens pt ON pt.id = mw.token_id
                """
            ).fetchall()
            distinct_mints = {row[0] for row in rows}
        finally:
            conn.close()
        self.assertEqual(
            len(distinct_mints), 3,
            f"There must be exactly 3 distinct token mints in memory windows;"
            f" got: {distinct_mints}",
        )
        self.assertIn(_MINT_A, distinct_mints)
        self.assertIn(_MINT_B, distinct_mints)
        self.assertIn(_MINT_C, distinct_mints)

    def test_token_mints_in_reports_match_list(self):
        """Mints in each report must match the token list order."""
        r = self._run(cycle_budget=3)
        self.assertEqual(r["token_a_report"]["mint"], _MINT_A)
        self.assertEqual(r["token_b_report"]["mint"], _MINT_B)
        self.assertEqual(r["token_c_report"]["mint"], _MINT_C)


# ---------------------------------------------------------------------------
# 7. Hard lock and financial gate tests
# ---------------------------------------------------------------------------

class TestLaneX4HardLocks(_DbBase):
    """All financial locks must remain set and no forbidden rows created."""

    def test_hard_locks_count_is_23(self):
        self.assertEqual(len(_HARD_LOCKS), 23)

    def test_all_hard_locks_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"_HARD_LOCKS[{key!r}] must be True")

    def test_no_x5_expansion_lock_present(self):
        self.assertIn("no_x5_expansion", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_x5_expansion"])

    def test_hard_locks_in_result_all_true(self):
        r = self._run(cycle_budget=1)
        hl = r.get("hard_locks", {})
        for key in _HARD_LOCKS:
            self.assertIn(key, hl, f"hard_locks missing key: {key}")
            self.assertTrue(hl[key], f"hard_locks[{key!r}] in result must be True")

    def test_buy_enabled_false(self):
        r = self._run(cycle_budget=1)
        self.assertFalse(r["buy_enabled"])

    def test_sell_enabled_false(self):
        r = self._run(cycle_budget=1)
        self.assertFalse(r["sell_enabled"])

    def test_hold_enabled_false(self):
        r = self._run(cycle_budget=1)
        self.assertFalse(r["hold_enabled"])

    def test_paper_decisions_zero(self):
        r = self._run(cycle_budget=3)
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_positions_zero(self):
        r = self._run(cycle_budget=3)
        self.assertEqual(r["positions_created"], 0)

    def test_trade_events_zero(self):
        r = self._run(cycle_budget=3)
        self.assertEqual(r["trade_events_created"], 0)

    def test_paper_trade_audits_zero(self):
        r = self._run(cycle_budget=3)
        self.assertEqual(r["paper_trade_audits_created"], 0)

    def test_pnl_zero(self):
        r = self._run(cycle_budget=3)
        self.assertEqual(r["pnl_created"], 0)

    def test_retrieval_rows_zero(self):
        r = self._run(cycle_budget=3)
        self.assertEqual(r["retrieval_rows_created"], 0)

    def test_forbidden_table_counts_all_zero(self):
        r = self._run(cycle_budget=3)
        fc = r.get("forbidden_table_counts", {})
        for table, count in fc.items():
            self.assertEqual(count, 0, f"Forbidden table {table!r} must have 0 rows")

    def test_retrieval_candidates_not_written(self):
        self._run(cycle_budget=3)
        self.assertEqual(self._count_rows("printer_retrieval_candidates"), 0)

    def test_retrieval_results_not_written(self):
        self._run(cycle_budget=3)
        self.assertEqual(self._count_rows("printer_retrieval_results"), 0)

    def test_paper_decisions_not_written(self):
        self._run(cycle_budget=3)
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_paper_positions_not_written(self):
        self._run(cycle_budget=3)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)


# ---------------------------------------------------------------------------
# 8. Constants and importability tests
# ---------------------------------------------------------------------------

class TestLaneX4Constants(unittest.TestCase):

    def test_exact_token_count_is_3(self):
        self.assertEqual(LANE_X4_EXACT_TOKEN_COUNT, 3)

    def test_command_name_is_string(self):
        self.assertIsInstance(LANE_X4_COMMAND_NAME, str)
        self.assertGreater(len(LANE_X4_COMMAND_NAME), 0)

    def test_status_constants_are_strings(self):
        for const in [LANE_X4_STATUS_COMPLETED, LANE_X4_STATUS_BLOCKED, LANE_X4_STATUS_STOPPED]:
            self.assertIsInstance(const, str)

    def test_module_importable(self):
        import printer_v1.operator_cli.lane_x4_three_token_runner as mod
        self.assertTrue(hasattr(mod, "run_three_token_memory_factory_cycle"))

    def test_functions_importable(self):
        from printer_v1.operator_cli.lane_x4_three_token_runner import (  # noqa: F401
            _load_and_validate_three_token_list,
            run_three_token_memory_factory_cycle,
        )

    def test_hard_locks_dict_has_expected_keys(self):
        expected_keys = {
            "no_buy_sell_hold",
            "no_paper_decisions",
            "no_positions",
            "no_pnl",
            "no_retrieval_activation",
            "no_live_trading",
            "no_paid_api",
            "no_wallet_private_key",
            "no_generic_search",
            "no_unbounded_loop",
            "no_daemon_mode",
            "no_scheduler_bypass",
            "no_source_governor_bypass",
            "no_ad_hoc_api_loop",
            "no_direct_adapter_call",
            "no_scoring_ranking_confidence",
            "no_embeddings_vectors",
            "no_1h_4h_12h_24h_collection",
            "no_5m_main_window",
            "no_trade_events",
            "no_paper_trade_audits",
            "no_token_pair_mixing",
            "no_x5_expansion",
        }
        missing = expected_keys - _HARD_LOCKS.keys()
        self.assertFalse(missing, f"Missing hard lock keys: {missing}")


# ---------------------------------------------------------------------------
# 9. CLI tests
# ---------------------------------------------------------------------------

class TestLaneX4CLI(unittest.TestCase):

    def test_cli_function_importable(self):
        from printer_v1.operator_cli.commands import main_run_lane_x4_three_token_cycle
        self.assertTrue(callable(main_run_lane_x4_three_token_cycle))

    def test_cli_blocked_without_operator_approved(self):
        """Missing --operator-approved → exits 0 with BLOCKED status in JSON."""
        from printer_v1.operator_cli.commands import main_run_lane_x4_three_token_cycle

        with tempfile.TemporaryDirectory() as tmp:
            db_path = pathlib.Path(tmp) / "test.sqlite3"
            backup_path = pathlib.Path(tmp) / "backup.sqlite3"
            token_path = pathlib.Path(tmp) / "tokens.json"
            backup_path.write_bytes(b"backup")
            apply_migrations(db_path)
            token_path.write_text(json.dumps({
                "tokens": [
                    {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                     "chain": "solana", "tracking_lane": "TRACK_FAST",
                     "operator_approved": True},
                    {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                     "chain": "solana", "tracking_lane": "TRACK_FAST",
                     "operator_approved": True},
                    {"token_mint": _MINT_C, "pair_address": _PAIR_C,
                     "chain": "solana", "tracking_lane": "TRACK_FAST",
                     "operator_approved": True},
                ]
            }), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main_run_lane_x4_three_token_cycle([
                    "--token-list-path", str(token_path),
                    "--backup-proof-path", str(backup_path),
                    "--db-path", str(db_path),
                ])
            self.assertEqual(rc, 0, "CLI should exit 0 even when BLOCKED")
            output = json.loads(buf.getvalue())
            self.assertEqual(output["lane_x4_status"], LANE_X4_STATUS_BLOCKED)

    def test_pyproject_entry_exists(self):
        """pyproject.toml must declare the Lane X4 CLI entry point."""
        pyproject = pathlib.Path(__file__).parent.parent / "pyproject.toml"
        if pyproject.exists():
            content = pyproject.read_text(encoding="utf-8")
            self.assertIn("printer-run-lane-x4-three-token-cycle", content)


# ---------------------------------------------------------------------------
# 10. Lane X2 regression tests — X4 must not break X2
# ---------------------------------------------------------------------------

class TestLaneX4X2Regression(unittest.TestCase):
    """Verify Lane X2 still works correctly after Lane X4 is added."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_proof_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _make_x2_adapter_map(self):
        return {
            _MINT_A: _build_adapter(_MINT_A, _PAIR_A),
            _MINT_B: _build_adapter(_MINT_B, _PAIR_B),
        }

    def _write_x2_token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens_x2_regression.json"
        tf.write_text(json.dumps({
            "tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ]
        }), encoding="utf-8")
        return tf

    def test_x2_still_completes_two_token_cycle(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import (
            LANE_X2_STATUS_COMPLETED,
            run_two_token_memory_factory_cycle,
        )
        r = run_two_token_memory_factory_cycle(
            self._write_x2_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=self._make_x2_adapter_map(),
            _cycle_budget=2,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_COMPLETED)

    def test_x2_still_rejects_three_tokens(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import (
            LANE_X2_STATUS_BLOCKED,
            run_two_token_memory_factory_cycle,
        )
        tf = pathlib.Path(self._tmp.name) / "three_tokens.json"
        tf.write_text(json.dumps({
            "tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_C, "pair_address": _PAIR_C,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ]
        }), encoding="utf-8")
        r = run_two_token_memory_factory_cycle(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            _adapter_map=self._make_x2_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_x2_token_count_unchanged(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import LANE_X2_EXACT_TOKEN_COUNT
        self.assertEqual(LANE_X2_EXACT_TOKEN_COUNT, 2)

    def test_x2_hard_locks_count_is_22(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import _HARD_LOCKS as x2_locks
        self.assertEqual(len(x2_locks), 22, "X2 must still have exactly 22 hard locks")

    def test_x2_buy_sell_hold_false(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import run_two_token_memory_factory_cycle
        r = run_two_token_memory_factory_cycle(
            self._write_x2_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=self._make_x2_adapter_map(),
            _cycle_budget=1,
        )
        self.assertFalse(r["buy_enabled"])
        self.assertFalse(r["sell_enabled"])
        self.assertFalse(r["hold_enabled"])

    def test_x2_forbidden_tables_zero(self):
        from printer_v1.operator_cli.lane_x2_two_token_runner import run_two_token_memory_factory_cycle
        r = run_two_token_memory_factory_cycle(
            self._write_x2_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter_map=self._make_x2_adapter_map(),
            _cycle_budget=2,
        )
        for table, count in r.get("forbidden_table_counts", {}).items():
            self.assertEqual(count, 0, f"X2 forbidden table {table!r} must be 0")


# ---------------------------------------------------------------------------
# 11. Lane X3 regression tests — X4 must not break X3
# ---------------------------------------------------------------------------

class TestLaneX4X3Regression(unittest.TestCase):
    """Verify Lane X3 lifecycle still works correctly after Lane X4 is added."""

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

    def test_x3_gate_blocks_cooldown_token(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
        )
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A])
        self.assertTrue(len(blocked) > 0, "X3 gate must block cooldown token")

    def test_x3_reopen_still_works(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            LANE_X3_STATUS_REOPENED,
            enter_cooldown_after_window,
            reopen_token,
        )
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        r = reopen_token(self.db_path, _MINT_A, _PAIR_A)
        self.assertEqual(r["lane_x3_status"], LANE_X3_STATUS_REOPENED)

    def test_x3_gate_passes_after_reopen(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
            reopen_token,
        )
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        reopen_token(self.db_path, _MINT_A, _PAIR_A)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A])
        self.assertEqual(len(blocked), 0, "X3 gate must pass after reopen")

    def test_x3_hard_locks_count_is_23(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import _HARD_LOCKS as x3_locks
        self.assertEqual(len(x3_locks), 23, "X3 must still have exactly 23 hard locks")


if __name__ == "__main__":
    unittest.main()
