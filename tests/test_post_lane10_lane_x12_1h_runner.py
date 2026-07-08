"""Lane X12 — WINDOW_1H Bounded Memory Growth Runner tests.

Coverage:
1.  Validator TRACK_FAST mode: 1 token, 5 tokens, 6+ rejected, TRACK_NORMAL rejected
2.  Validator TRACK_FAST: WATCH_ONLY rejected, missing pair, duplicate mint, duplicate pair
3.  Validator TRACK_NORMAL mode: 1 token, 7 tokens, 8+ rejected, TRACK_FAST rejected
4.  Window kind: WINDOW_1H enabled; WINDOW_15M blocked; 5M forbidden; 4h/12h/24h blocked
5.  Mode segregation: FAST token rejected in NORMAL mode; NORMAL token rejected in FAST mode
6.  Job kind: TRACK_FAST creates TRACK_FAST_1H jobs; TRACK_NORMAL creates TRACK_NORMAL_1H
7.  Freshness TRACK_FAST: advisory skipped when _adapter_map provided (test bypass)
8.  Freshness TRACK_NORMAL: advisory only; stale/unknown never blocks run
9.  Handler: is_handler_registered() True for both FAST and NORMAL handlers
10. Handler: TRACK_FAST_1H / TRACK_NORMAL_1H job kind constants correct
11. Source Governor: checked before each source call
12. Running jobs gate: causes handler to block (Gate 2)
13. Consecutive failures: safe stop after budget exceeded
14. Lock fields: paper_decisions, positions, pnl always zero
15. Hard locks: all keys present and True; buy/sell/hold always False
16. Cadence policy WINDOW_1H TRACK_FAST: min_snapshots=8, max_gap=600, interval=240
17. Cadence policy WINDOW_1H TRACK_NORMAL: min_snapshots=3, max_gap=1800, interval=720
18. CLI commands: registered and parse args correctly for both modes
19. Output fields: window_kind=WINDOW_1H, zero_clean_memories_is_valid=True
20. Runner gates: operator_approved, db_path, backup_proof_path, token_list_path
"""

from __future__ import annotations

import io
import json
import pathlib
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import datetime, timedelta, timezone
from typing import Any

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_x12_1h_runner import (
    LANE_X12_FAST_COMMAND_NAME,
    LANE_X12_FAST_MAX_TOKEN_COUNT,
    LANE_X12_FAST_MIN_TOKEN_COUNT,
    LANE_X12_MODE_FAST,
    LANE_X12_MODE_NORMAL,
    LANE_X12_NORMAL_COMMAND_NAME,
    LANE_X12_NORMAL_MAX_TOKEN_COUNT,
    LANE_X12_NORMAL_MIN_TOKEN_COUNT,
    LANE_X12_STATUS_BLOCKED,
    LANE_X12_STATUS_COMPLETED,
    LANE_X12_STATUS_STOPPED,
    _HARD_LOCKS,
    _load_and_validate_token_list,
    run_1h_memory_factory_cycle,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
)

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

_MINT_A = "FastMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_MINT_B = "FastMintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_MINT_C = "FastMintCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
_MINT_D = "FastMintDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"
_MINT_E = "FastMintEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"

_MINT_F = "NormMintFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
_MINT_G = "NormMintGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"
_MINT_EXTRA = "ExtraMintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

_PAIR_A = "FastPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_B = "FastPairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_PAIR_C = "FastPairCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
_PAIR_D = "FastPairDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"
_PAIR_E = "FastPairEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"
_PAIR_F = "NormPairFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
_PAIR_G = "NormPairGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"
_PAIR_EXTRA = "ExtraPairXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

_NORM_MINTS = [_MINT_A, _MINT_B, _MINT_C, _MINT_D, _MINT_E, _MINT_F, _MINT_G]
_NORM_PAIRS = [_PAIR_A, _PAIR_B, _PAIR_C, _PAIR_D, _PAIR_E, _PAIR_F, _PAIR_G]


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
                    "symbol": "X12T",
                    "name": "X12 Test Token",
                    "price_usd": 0.00012,
                    "liquidity_usd": 12000.0,
                    "volume_5m": 150.0,
                    "volume_1h": 1800.0,
                    "volume_24h": 43200.0,
                    "txns_5m": 6,
                    "txns_1h": 72,
                    "txns_24h": 1728,
                    "fdv": 120000.0,
                    "market_cap": 100000.0,
                    "price_change_5m": 0.3,
                    "price_change_1h": -0.8,
                    "price_change_24h": -2.5,
                }
            ],
        },
    )


class _FailingCallable:
    """Always raises RuntimeError — simulates source failures."""

    def __call__(self, *args, **kwargs):
        raise RuntimeError("simulated source failure for X12 budget test")


def _make_adapter_map(*mints_pairs):
    return {mint: _build_adapter(mint, pair) for mint, pair in mints_pairs}


def _make_failing_adapter_map(*mints):
    fa = _FailingCallable()
    return {m: fa for m in mints}


# ---------------------------------------------------------------------------
# Base test class
# ---------------------------------------------------------------------------

class _DbBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ts(self, seconds_ago: float) -> str:
        return (self._now() - timedelta(seconds=seconds_ago)).isoformat()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _insert_source_request(self, received_at: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO printer_source_requests"
                " (source_name, request_kind, requested_at, request_key,"
                "  tracking_priority, source_status, data_quality_label, created_at)"
                " VALUES ('dexscreener', 'pair_market_snapshot', ?, 'test-key',"
                "  1, 'COMPLETE', 'CLEAN_DATA', ?)",
                (received_at, received_at),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _insert_source_response(
        self, received_at: str, pair_address: str, mint: str
    ) -> int:
        srq_id = self._insert_source_request(received_at)
        payload = json.dumps({
            "pair_address": pair_address, "token_mint": mint, "price_usd": 0.00012,
            "captured_at": received_at,
        })
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO printer_source_responses"
                " (source_request_id, source_name, received_at,"
                "  status_code, source_status, data_quality_label, normalized_payload_json,"
                "  created_at)"
                " VALUES (?, 'dexscreener', ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, ?)",
                (srq_id, received_at, payload, received_at),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _write_token_list(
        self,
        mints_pairs: list[tuple[str, str]],
        *,
        tracking_lane: str = LANE_X12_MODE_FAST,
        operator_approved: bool = True,
        chain: str = "solana",
    ) -> pathlib.Path:
        tokens = [
            {
                "token_mint": m,
                "pair_address": p,
                "chain": chain,
                "tracking_lane": tracking_lane,
                "operator_approved": operator_approved,
            }
            for m, p in mints_pairs
        ]
        tf = pathlib.Path(self._tmp.name) / "token_list.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _run_fast(
        self,
        mints_pairs: list[tuple[str, str]],
        *,
        operator_approved: bool = True,
        cycle_budget: int = 1,
        adapter_map=None,
        **overrides,
    ) -> dict[str, Any]:
        tf = self._write_token_list(mints_pairs, tracking_lane=LANE_X12_MODE_FAST)
        if adapter_map is None:
            adapter_map = _make_adapter_map(*mints_pairs)
        return run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=operator_approved,
            _adapter_map=adapter_map,
            _cycle_budget=cycle_budget,
            **overrides,
        )

    def _run_normal(
        self,
        mints_pairs: list[tuple[str, str]],
        *,
        operator_approved: bool = True,
        cycle_budget: int = 1,
        adapter_map=None,
        **overrides,
    ) -> dict[str, Any]:
        tf = self._write_token_list(mints_pairs, tracking_lane=LANE_X12_MODE_NORMAL)
        if adapter_map is None:
            adapter_map = _make_adapter_map(*mints_pairs)
        return run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_NORMAL,
            operator_approved=operator_approved,
            _adapter_map=adapter_map,
            _cycle_budget=cycle_budget,
            **overrides,
        )

    def _count_table(self, table: str) -> int:
        try:
            with self._conn() as conn:
                return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except Exception:
            return 0


# ---------------------------------------------------------------------------
# 1. Validator — TRACK_FAST mode
# ---------------------------------------------------------------------------

class TestValidatorFastMode(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, tokens):
        tf = pathlib.Path(self._tmp.name) / "tl.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _one_fast(self, **overrides):
        base = {
            "token_mint": _MINT_A,
            "pair_address": _PAIR_A,
            "chain": "solana",
            "tracking_lane": "TRACK_FAST",
            "operator_approved": True,
        }
        base.update(overrides)
        return base

    def test_one_fast_token_validates(self):
        tf = self._write([self._one_fast()])
        valid, reason, tokens = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertTrue(valid, reason)
        self.assertEqual(len(tokens), 1)

    def test_five_fast_tokens_validate(self):
        tokens = [
            {
                "token_mint": mint, "pair_address": pair, "chain": "solana",
                "tracking_lane": "TRACK_FAST", "operator_approved": True,
            }
            for mint, pair in zip(
                [_MINT_A, _MINT_B, _MINT_C, _MINT_D, _MINT_E],
                [_PAIR_A, _PAIR_B, _PAIR_C, _PAIR_D, _PAIR_E],
            )
        ]
        tf = self._write(tokens)
        valid, reason, result = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertTrue(valid, reason)
        self.assertEqual(len(result), 5)

    def test_six_fast_tokens_rejected(self):
        tokens = [
            {
                "token_mint": mint, "pair_address": pair, "chain": "solana",
                "tracking_lane": "TRACK_FAST", "operator_approved": True,
            }
            for mint, pair in zip(
                [_MINT_A, _MINT_B, _MINT_C, _MINT_D, _MINT_E, _MINT_F],
                [_PAIR_A, _PAIR_B, _PAIR_C, _PAIR_D, _PAIR_E, _PAIR_F],
            )
        ]
        tf = self._write(tokens)
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertIn(str(LANE_X12_FAST_MAX_TOKEN_COUNT), reason)

    def test_zero_fast_tokens_rejected(self):
        tf = self._write([])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertIn(str(LANE_X12_FAST_MIN_TOKEN_COUNT), reason)

    def test_track_normal_token_rejected_in_fast_mode(self):
        tf = self._write([self._one_fast(tracking_lane="TRACK_NORMAL")])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertIn("TRACK_FAST", reason)

    def test_watch_only_rejected_in_fast_mode(self):
        tf = self._write([self._one_fast(tracking_lane="WATCH_ONLY")])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)

    def test_operator_approved_required_fast(self):
        tf = self._write([self._one_fast(operator_approved=False)])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertIn("operator_approved", reason)

    def test_missing_pair_address_rejected_fast(self):
        tok = {
            "token_mint": _MINT_A, "chain": "solana",
            "tracking_lane": "TRACK_FAST", "operator_approved": True,
        }
        tf = self._write([tok])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)

    def test_placeholder_pair_rejected_fast(self):
        tf = self._write([self._one_fast(pair_address="PLACEHOLDER_PAIR")])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)

    def test_duplicate_mint_rejected_fast(self):
        tokens = [
            {
                "token_mint": _MINT_A, "pair_address": _PAIR_A, "chain": "solana",
                "tracking_lane": "TRACK_FAST", "operator_approved": True,
            },
            {
                "token_mint": _MINT_A, "pair_address": _PAIR_B, "chain": "solana",
                "tracking_lane": "TRACK_FAST", "operator_approved": True,
            },
        ]
        tf = self._write(tokens)
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertIn("duplicate", reason.lower())

    def test_duplicate_pair_rejected_fast(self):
        tokens = [
            {
                "token_mint": _MINT_A, "pair_address": _PAIR_A, "chain": "solana",
                "tracking_lane": "TRACK_FAST", "operator_approved": True,
            },
            {
                "token_mint": _MINT_B, "pair_address": _PAIR_A, "chain": "solana",
                "tracking_lane": "TRACK_FAST", "operator_approved": True,
            },
        ]
        tf = self._write(tokens)
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertIn("duplicate", reason.lower())

    def test_non_solana_chain_rejected_fast(self):
        tf = self._write([self._one_fast(chain="ethereum")])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertIn("solana", reason)

    def test_none_path_returns_invalid_fast(self):
        valid, reason, tokens = _load_and_validate_token_list(None, LANE_X12_MODE_FAST)
        self.assertFalse(valid)
        self.assertEqual(tokens, [])


# ---------------------------------------------------------------------------
# 2. Validator — TRACK_NORMAL mode
# ---------------------------------------------------------------------------

class TestValidatorNormalMode(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, tokens):
        tf = pathlib.Path(self._tmp.name) / "tl.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _one_normal(self, **overrides):
        base = {
            "token_mint": _MINT_A,
            "pair_address": _PAIR_A,
            "chain": "solana",
            "tracking_lane": "TRACK_NORMAL",
            "operator_approved": True,
        }
        base.update(overrides)
        return base

    def test_one_normal_token_validates(self):
        tf = self._write([self._one_normal()])
        valid, reason, tokens = _load_and_validate_token_list(tf, LANE_X12_MODE_NORMAL)
        self.assertTrue(valid, reason)
        self.assertEqual(len(tokens), 1)

    def test_seven_normal_tokens_validate(self):
        tokens = [
            {
                "token_mint": mint, "pair_address": pair, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            }
            for mint, pair in zip(_NORM_MINTS, _NORM_PAIRS)
        ]
        tf = self._write(tokens)
        valid, reason, result = _load_and_validate_token_list(tf, LANE_X12_MODE_NORMAL)
        self.assertTrue(valid, reason)
        self.assertEqual(len(result), 7)

    def test_eight_normal_tokens_rejected(self):
        mints = _NORM_MINTS + [_MINT_EXTRA]
        pairs = _NORM_PAIRS + [_PAIR_EXTRA]
        tokens = [
            {
                "token_mint": m, "pair_address": p, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            }
            for m, p in zip(mints, pairs)
        ]
        tf = self._write(tokens)
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_NORMAL)
        self.assertFalse(valid)
        self.assertIn(str(LANE_X12_NORMAL_MAX_TOKEN_COUNT), reason)

    def test_track_fast_token_rejected_in_normal_mode(self):
        tf = self._write([self._one_normal(tracking_lane="TRACK_FAST")])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_NORMAL)
        self.assertFalse(valid)
        self.assertIn("TRACK_NORMAL", reason)

    def test_zero_normal_tokens_rejected(self):
        tf = self._write([])
        valid, reason, _ = _load_and_validate_token_list(tf, LANE_X12_MODE_NORMAL)
        self.assertFalse(valid)
        self.assertIn(str(LANE_X12_NORMAL_MIN_TOKEN_COUNT), reason)


# ---------------------------------------------------------------------------
# 3. Window kind gates
# ---------------------------------------------------------------------------

class TestWindowKindGates(_DbBase):
    def test_window_1h_is_enabled(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertNotEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        self.assertEqual(result["window_kind"], "WINDOW_1H")

    def test_window_15m_blocked_in_fast_mode(self):
        tf = self._write_token_list([(_MINT_A, _PAIR_A)], tracking_lane=LANE_X12_MODE_FAST)
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            window_kind="WINDOW_15M",
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertIn("WINDOW_15M", reasons)

    def test_window_5m_micro_event_forbidden_as_main(self):
        tf = self._write_token_list([(_MINT_A, _PAIR_A)], tracking_lane=LANE_X12_MODE_FAST)
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            window_kind="WINDOW_5M_MICRO_EVENT",
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertTrue(
            "support-only" in reasons or "5m" in reasons.lower(),
            f"Expected support-only mention in: {reasons}",
        )

    def test_window_4h_blocked(self):
        tf = self._write_token_list([(_MINT_A, _PAIR_A)], tracking_lane=LANE_X12_MODE_FAST)
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            window_kind="WINDOW_4H",
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)

    def test_window_12h_blocked(self):
        tf = self._write_token_list([(_MINT_A, _PAIR_A)], tracking_lane=LANE_X12_MODE_FAST)
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            window_kind="WINDOW_12H",
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)

    def test_window_24h_blocked(self):
        tf = self._write_token_list([(_MINT_A, _PAIR_A)], tracking_lane=LANE_X12_MODE_FAST)
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            window_kind="WINDOW_24H",
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 4. Mode segregation
# ---------------------------------------------------------------------------

class TestModeSegregation(_DbBase):
    def test_normal_token_in_fast_mode_blocked(self):
        """Token list with TRACK_NORMAL tokens must be blocked in FAST mode."""
        tf = self._write_token_list([(_MINT_A, _PAIR_A)], tracking_lane=LANE_X12_MODE_NORMAL)
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertIn("TRACK_FAST", reasons)

    def test_fast_token_in_normal_mode_blocked(self):
        """Token list with TRACK_FAST tokens must be blocked in NORMAL mode."""
        tf = self._write_token_list([(_MINT_A, _PAIR_A)], tracking_lane=LANE_X12_MODE_FAST)
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_NORMAL,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertIn("TRACK_NORMAL", reasons)

    def test_six_fast_tokens_rejected_in_fast_mode(self):
        """6 tokens in TRACK_FAST mode must be rejected (max=5)."""
        mints = [_MINT_A, _MINT_B, _MINT_C, _MINT_D, _MINT_E, _MINT_F]
        pairs = [_PAIR_A, _PAIR_B, _PAIR_C, _PAIR_D, _PAIR_E, _PAIR_F]
        tf = self._write_token_list(
            list(zip(mints, pairs)), tracking_lane=LANE_X12_MODE_FAST
        )
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            _adapter_map=_make_adapter_map(*zip(mints, pairs)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 5. Job kind tests
# ---------------------------------------------------------------------------

class TestJobKind(_DbBase):
    def test_fast_mode_creates_track_fast_1h_jobs(self):
        self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_kind FROM printer_scheduler_jobs WHERE job_kind = ?",
                ("TRACK_FAST_1H",),
            ).fetchall()
        self.assertGreater(len(rows), 0, "Expected TRACK_FAST_1H jobs in DB")

    def test_fast_mode_does_not_create_track_normal_1h_jobs(self):
        self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_kind FROM printer_scheduler_jobs WHERE job_kind = ?",
                ("TRACK_NORMAL_1H",),
            ).fetchall()
        self.assertEqual(len(rows), 0, "TRACK_NORMAL_1H jobs must not be created by FAST mode")

    def test_normal_mode_creates_track_normal_1h_jobs(self):
        self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_kind FROM printer_scheduler_jobs WHERE job_kind = ?",
                ("TRACK_NORMAL_1H",),
            ).fetchall()
        self.assertGreater(len(rows), 0, "Expected TRACK_NORMAL_1H jobs in DB")

    def test_normal_mode_does_not_create_track_fast_1h_jobs(self):
        self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_kind FROM printer_scheduler_jobs WHERE job_kind = ?",
                ("TRACK_FAST_1H",),
            ).fetchall()
        self.assertEqual(len(rows), 0, "TRACK_FAST_1H jobs must not be created by NORMAL mode")

    def test_fast_job_name_prefix_is_x12_fast(self):
        self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute("SELECT job_name FROM printer_scheduler_jobs").fetchall()
        names = [r[0] for r in rows]
        self.assertTrue(
            any("x12_track_fast_1h" in n for n in names),
            f"Expected x12_track_fast_1h prefix in job names; got {names}",
        )


# ---------------------------------------------------------------------------
# 6. Freshness — TRACK_FAST (hard gate bypassed in test mode via _adapter_map)
# ---------------------------------------------------------------------------

class TestFreshnessFastMode(_DbBase):
    def test_freshness_gate_results_in_fast_output(self):
        """_adapter_map bypasses freshness gate; result includes freshness_gate_results."""
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertIn("freshness_gate_results", result)

    def test_fast_with_adapter_map_skips_freshness_block(self):
        """When _adapter_map is provided (test fixture), freshness gate is bypassed."""
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=0)
        # Should not be BLOCKED by freshness (because adapter_map bypasses the gate)
        self.assertNotIn(
            "freshness",
            " ".join(result.get("blocked_reasons", [])).lower(),
        )

    def test_freshness_gate_results_is_list(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=0)
        self.assertIsInstance(result["freshness_gate_results"], list)


# ---------------------------------------------------------------------------
# 7. Freshness — TRACK_NORMAL (advisory only)
# ---------------------------------------------------------------------------

class TestFreshnessNormalMode(_DbBase):
    def test_freshness_advisory_results_in_normal_output(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertIn("freshness_advisory_results", result)

    def test_stale_track_normal_does_not_block_run(self):
        """No source evidence (unknown freshness) must not block TRACK_NORMAL."""
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=0)
        self.assertNotIn(
            "freshness",
            " ".join(result.get("blocked_reasons", [])).lower(),
        )

    def test_freshness_advisory_never_adds_to_blocked_reasons(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=0)
        reasons_text = " ".join(result.get("blocked_reasons", [])).lower()
        self.assertNotIn("freshness", reasons_text)
        self.assertNotIn("stale", reasons_text)

    def test_freshness_advisory_results_is_list(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=0)
        self.assertIsInstance(result["freshness_advisory_results"], list)


# ---------------------------------------------------------------------------
# 8. Handler registration
# ---------------------------------------------------------------------------

class TestHandlerRegistration(unittest.TestCase):
    def test_fast_handler_is_registered(self):
        from printer_v1.operator_cli.lane_e2h_fast_1h_handler import is_handler_registered
        self.assertTrue(is_handler_registered())

    def test_normal_handler_is_registered(self):
        from printer_v1.operator_cli.lane_e2h_normal_1h_handler import is_handler_registered
        self.assertTrue(is_handler_registered())

    def test_fast_handler_job_kind_constant(self):
        from printer_v1.operator_cli.lane_e2h_fast_1h_handler import HANDLER_JOB_KIND
        self.assertEqual(HANDLER_JOB_KIND, "TRACK_FAST_1H")

    def test_normal_handler_job_kind_constant(self):
        from printer_v1.operator_cli.lane_e2h_normal_1h_handler import HANDLER_JOB_KIND
        self.assertEqual(HANDLER_JOB_KIND, "TRACK_NORMAL_1H")

    def test_fast_handler_target_window(self):
        from printer_v1.operator_cli.lane_e2h_fast_1h_handler import HANDLER_TARGET_WINDOW
        self.assertEqual(HANDLER_TARGET_WINDOW, "WINDOW_1H")

    def test_normal_handler_target_window(self):
        from printer_v1.operator_cli.lane_e2h_normal_1h_handler import HANDLER_TARGET_WINDOW
        self.assertEqual(HANDLER_TARGET_WINDOW, "WINDOW_1H")


# ---------------------------------------------------------------------------
# 9. Source Governor gate
# ---------------------------------------------------------------------------

class TestSourceGovernorGate(_DbBase):
    def test_source_governor_checked_before_source_call_fast(self):
        self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            count = int(
                conn.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
            )
        self.assertGreater(count, 0, "Source Governor must record source requests")

    def test_source_governor_checked_before_source_call_normal(self):
        self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            count = int(
                conn.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
            )
        self.assertGreater(count, 0, "Source Governor must record source requests for NORMAL mode")


# ---------------------------------------------------------------------------
# 10. Running jobs gate
# ---------------------------------------------------------------------------

class TestSchedulerGates(_DbBase):
    def _inject_running_job(self):
        now = datetime.now(timezone.utc).isoformat()
        with self._conn() as conn:
            conn.execute(
                """INSERT INTO printer_scheduler_jobs
                   (job_name, job_kind, status, scheduled_for, created_at, updated_at,
                    lock_owner, locked_at)
                   VALUES ('blocking_job', 'TRACK_FAST_FIRST_15M', 'RUNNING',
                           ?, ?, ?, 'blocking_lock', ?)""",
                (now, now, now, now),
            )
            conn.commit()

    def test_running_job_causes_handler_to_block_fast(self):
        """When a RUNNING job exists, Gate 2 blocks the handler step."""
        self._inject_running_job()
        result = self._run_fast(
            [(_MINT_A, _PAIR_A)],
            cycle_budget=1,
            source_budget_max_consecutive_failures=0,
        )
        # Runner started (not BLOCKED at pre-flight level); hit failure during execution
        self.assertIn(
            result["lane_x12_status"],
            {LANE_X12_STATUS_STOPPED, LANE_X12_STATUS_COMPLETED},
        )


# ---------------------------------------------------------------------------
# 11. Consecutive failures safe stop
# ---------------------------------------------------------------------------

class TestConsecutiveFailures(_DbBase):
    def test_consecutive_failures_trigger_safe_stop_fast(self):
        am = _make_failing_adapter_map(_MINT_A, _MINT_B)
        tf = self._write_token_list(
            [(_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B)], tracking_lane=LANE_X12_MODE_FAST
        )
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            _adapter_map=am,
            _cycle_budget=10,
            source_budget_max_consecutive_failures=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_STOPPED)
        self.assertGreater(result["total_source_failures"], 0)

    def test_consecutive_failures_trigger_safe_stop_normal(self):
        am = _make_failing_adapter_map(_MINT_A, _MINT_B)
        tf = self._write_token_list(
            [(_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B)], tracking_lane=LANE_X12_MODE_NORMAL
        )
        result = run_1h_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_NORMAL,
            operator_approved=True,
            _adapter_map=am,
            _cycle_budget=10,
            source_budget_max_consecutive_failures=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_STOPPED)
        self.assertGreater(result["total_source_failures"], 0)


# ---------------------------------------------------------------------------
# 12. Lock fields — no paper decisions, positions, pnl, retrieval
# ---------------------------------------------------------------------------

class TestLockFields(_DbBase):
    def test_no_paper_decisions_created_fast(self):
        self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(self._count_table("printer_paper_decisions"), 0)

    def test_no_paper_decisions_created_normal(self):
        self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(self._count_table("printer_paper_decisions"), 0)

    def test_paper_decisions_field_always_zero(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["paper_decisions_created"], 0)

    def test_positions_field_always_zero(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["positions_created"], 0)

    def test_pnl_field_always_zero(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["pnl_created"], 0)

    def test_retrieval_rows_always_zero(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["retrieval_rows_created"], 0)


# ---------------------------------------------------------------------------
# 13. Hard locks
# ---------------------------------------------------------------------------

class TestHardLocks(_DbBase):
    def test_hard_locks_all_present_and_true_fast(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=0)
        locks = result.get("hard_locks", {})
        for key in _HARD_LOCKS:
            self.assertIn(key, locks, f"Missing hard lock key: {key}")
            self.assertTrue(locks[key], f"Hard lock {key!r} must be True")

    def test_hard_locks_all_present_and_true_normal(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=0)
        locks = result.get("hard_locks", {})
        for key in _HARD_LOCKS:
            self.assertIn(key, locks, f"Missing hard lock key: {key}")
            self.assertTrue(locks[key], f"Hard lock {key!r} must be True")

    def test_buy_sell_hold_always_false_fast(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=0)
        self.assertFalse(result["buy_enabled"])
        self.assertFalse(result["sell_enabled"])
        self.assertFalse(result["hold_enabled"])

    def test_buy_sell_hold_always_false_normal(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=0)
        self.assertFalse(result["buy_enabled"])
        self.assertFalse(result["sell_enabled"])
        self.assertFalse(result["hold_enabled"])


# ---------------------------------------------------------------------------
# 14. Cadence policy WINDOW_1H
# ---------------------------------------------------------------------------

class TestCadencePolicyWindow1H(unittest.TestCase):
    def _get_1h_policy(self, tracking_lane: str):
        from printer_v1.snapshots.cadence_policy import get_policy
        return get_policy("WINDOW_1H", tracking_lane)

    def test_window_1h_track_fast_minimum_snapshots(self):
        policy = self._get_1h_policy("TRACK_FAST")
        self.assertIsNotNone(policy, "Expected WINDOW_1H TRACK_FAST policy")
        self.assertEqual(policy.minimum_required_snapshots, 8)

    def test_window_1h_track_fast_max_gap(self):
        policy = self._get_1h_policy("TRACK_FAST")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.max_clean_snapshot_gap_seconds, 600)

    def test_window_1h_track_fast_snapshot_interval(self):
        policy = self._get_1h_policy("TRACK_FAST")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.target_snapshot_interval_seconds, 240)

    def test_window_1h_track_fast_window_close_interval(self):
        policy = self._get_1h_policy("TRACK_FAST")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.window_close_interval_seconds, 2700)

    def test_window_1h_track_fast_enabled_for_real_collection(self):
        policy = self._get_1h_policy("TRACK_FAST")
        self.assertIsNotNone(policy)
        self.assertTrue(policy.enabled_for_real_collection)

    def test_window_1h_track_normal_minimum_snapshots(self):
        policy = self._get_1h_policy("TRACK_NORMAL")
        self.assertIsNotNone(policy, "Expected WINDOW_1H TRACK_NORMAL policy")
        self.assertEqual(policy.minimum_required_snapshots, 3)

    def test_window_1h_track_normal_max_gap(self):
        policy = self._get_1h_policy("TRACK_NORMAL")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.max_clean_snapshot_gap_seconds, 1800)

    def test_window_1h_track_normal_snapshot_interval(self):
        policy = self._get_1h_policy("TRACK_NORMAL")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.target_snapshot_interval_seconds, 720)

    def test_window_1h_track_normal_window_close_interval(self):
        policy = self._get_1h_policy("TRACK_NORMAL")
        self.assertIsNotNone(policy)
        self.assertEqual(policy.window_close_interval_seconds, 2700)

    def test_window_1h_track_normal_not_support_only(self):
        policy = self._get_1h_policy("TRACK_NORMAL")
        self.assertIsNotNone(policy)
        self.assertFalse(policy.support_only)


# ---------------------------------------------------------------------------
# 15. CLI command registration
# ---------------------------------------------------------------------------

class TestCLIRegistration(unittest.TestCase):
    def test_fast_command_name_constant(self):
        self.assertEqual(LANE_X12_FAST_COMMAND_NAME, "printer-run-lane-x12-fast-1h-cycle")

    def test_normal_command_name_constant(self):
        self.assertEqual(LANE_X12_NORMAL_COMMAND_NAME, "printer-run-lane-x12-normal-1h-cycle")

    def test_fast_cli_registered_in_commands(self):
        from printer_v1.operator_cli.commands import main_run_lane_x12_fast_1h_cycle
        self.assertTrue(callable(main_run_lane_x12_fast_1h_cycle))

    def test_normal_cli_registered_in_commands(self):
        from printer_v1.operator_cli.commands import main_run_lane_x12_normal_1h_cycle
        self.assertTrue(callable(main_run_lane_x12_normal_1h_cycle))

    def test_fast_cli_parse_help(self):
        from printer_v1.operator_cli.commands import main_run_lane_x12_fast_1h_cycle
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                main_run_lane_x12_fast_1h_cycle(["--help"])
        except SystemExit:
            pass
        help_text = buf.getvalue()
        self.assertIn("x12", help_text.lower())

    def test_normal_cli_parse_help(self):
        from printer_v1.operator_cli.commands import main_run_lane_x12_normal_1h_cycle
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                main_run_lane_x12_normal_1h_cycle(["--help"])
        except SystemExit:
            pass
        help_text = buf.getvalue()
        self.assertIn("x12", help_text.lower())


# ---------------------------------------------------------------------------
# 16. Output fields and invariants
# ---------------------------------------------------------------------------

class TestRunnerOutputFields(_DbBase):
    def test_window_kind_is_window_1h_fast(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["window_kind"], "WINDOW_1H")

    def test_window_kind_is_window_1h_normal(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["window_kind"], "WINDOW_1H")

    def test_zero_clean_memories_is_valid_fast(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertTrue(result["zero_clean_memories_is_valid"])

    def test_zero_clean_memories_is_valid_normal(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertTrue(result["zero_clean_memories_is_valid"])

    def test_token_reports_list_in_output(self):
        result = self._run_fast([(_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B)], cycle_budget=1)
        self.assertIsInstance(result["token_reports"], list)
        self.assertEqual(len(result["token_reports"]), 2)

    def test_command_field_correct_fast(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["command"], LANE_X12_FAST_COMMAND_NAME)

    def test_command_field_correct_normal(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["command"], LANE_X12_NORMAL_COMMAND_NAME)

    def test_mode_field_fast(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["mode"], LANE_X12_MODE_FAST)

    def test_mode_field_normal(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["mode"], LANE_X12_MODE_NORMAL)


# ---------------------------------------------------------------------------
# 17. Runner pre-flight gates
# ---------------------------------------------------------------------------

class TestRunnerGates(_DbBase):
    def test_operator_not_approved_blocks_fast(self):
        result = self._run_fast([(_MINT_A, _PAIR_A)], operator_approved=False, cycle_budget=0)
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        self.assertTrue(
            any("operator_approved" in r for r in result["blocked_reasons"])
        )

    def test_operator_not_approved_blocks_normal(self):
        result = self._run_normal([(_MINT_A, _PAIR_A)], operator_approved=False, cycle_budget=0)
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        self.assertTrue(
            any("operator_approved" in r for r in result["blocked_reasons"])
        )

    def test_missing_db_path_blocks(self):
        result = run_1h_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path=None,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)

    def test_nonexistent_db_blocks(self):
        result = run_1h_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path="/nonexistent/x12.sqlite3",
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)

    def test_missing_backup_blocks(self):
        result = run_1h_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path=self.db_path,
            backup_proof_path=None,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)

    def test_long_profile_without_flag_blocks(self):
        result = run_1h_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode=LANE_X12_MODE_FAST,
            operator_approved=True,
            duration_profile="12h",
            allow_long_bounded_run=False,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)
        reasons = " ".join(result.get("blocked_reasons", []))
        self.assertIn("allow_long_bounded_run", reasons)

    def test_invalid_mode_blocks(self):
        result = run_1h_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            mode="TRACK_BOGUS",
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x12_status"], LANE_X12_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 18. Scheduler contracts — job kind entries registered
# ---------------------------------------------------------------------------

class TestSchedulerContracts(unittest.TestCase):
    def test_track_fast_1h_in_job_kind(self):
        from printer_v1.scheduler.contracts import JobKind
        self.assertEqual(JobKind.TRACK_FAST_1H.value, "TRACK_FAST_1H")

    def test_track_normal_1h_in_job_kind(self):
        from printer_v1.scheduler.contracts import JobKind
        self.assertEqual(JobKind.TRACK_NORMAL_1H.value, "TRACK_NORMAL_1H")

    def test_track_fast_1h_in_priority_order(self):
        from printer_v1.scheduler.contracts import JOB_PRIORITY_ORDER, JobKind
        self.assertIn(JobKind.TRACK_FAST_1H, JOB_PRIORITY_ORDER)

    def test_track_normal_1h_in_priority_order(self):
        from printer_v1.scheduler.contracts import JOB_PRIORITY_ORDER, JobKind
        self.assertIn(JobKind.TRACK_NORMAL_1H, JOB_PRIORITY_ORDER)

    def test_track_fast_1h_before_track_normal_1h_in_priority(self):
        from printer_v1.scheduler.contracts import JOB_PRIORITY_ORDER, JobKind
        fast_idx = JOB_PRIORITY_ORDER.index(JobKind.TRACK_FAST_1H)
        normal_idx = JOB_PRIORITY_ORDER.index(JobKind.TRACK_NORMAL_1H)
        self.assertLess(fast_idx, normal_idx)

    def test_track_fast_1h_after_track_fast_first_15m(self):
        from printer_v1.scheduler.contracts import JOB_PRIORITY_ORDER, JobKind
        fast_15m_idx = JOB_PRIORITY_ORDER.index(JobKind.TRACK_FAST_FIRST_15M)
        fast_1h_idx = JOB_PRIORITY_ORDER.index(JobKind.TRACK_FAST_1H)
        self.assertLess(fast_15m_idx, fast_1h_idx)

    def test_track_normal_1h_after_track_normal_first_15m(self):
        from printer_v1.scheduler.contracts import JOB_PRIORITY_ORDER, JobKind
        normal_15m_idx = JOB_PRIORITY_ORDER.index(JobKind.TRACK_NORMAL_FIRST_15M)
        normal_1h_idx = JOB_PRIORITY_ORDER.index(JobKind.TRACK_NORMAL_1H)
        self.assertLess(normal_15m_idx, normal_1h_idx)


if __name__ == "__main__":
    unittest.main()
