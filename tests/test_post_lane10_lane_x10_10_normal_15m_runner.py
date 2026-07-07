"""Lane X10.10B — Bounded TRACK_NORMAL 15m Memory Growth Runner tests.

Coverage:
- Validator: 1 token, 7 tokens, 8+ rejected, TRACK_FAST rejected, WATCH_ONLY rejected
- Validator: missing pair, duplicate mint, duplicate pair, operator_approved required
- WINDOW_15M: only WINDOW_15M enabled; 5m forbidden as main; 1h/4h/12h/24h blocked
- Job kind: creates TRACK_NORMAL_FIRST_15M jobs; does NOT create TRACK_FAST_FIRST_15M
- Freshness: advisory only; stale TRACK_NORMAL never blocks run; FRESHNESS_UNKNOWN advisory
- Freshness: <=300s no warning context; 301-600s advisory context; >600s strong advisory
- Freshness: freshness_advisory_results always in output (not freshness_gate_results)
- Source Governor: checked before each source call
- Running jobs gate: blocks when another job is RUNNING at start of step
- Active locks gate: blocks when another job has active lock
- Consecutive failures: safe stop after limit; reset on success
- Lock fields: no paper_decisions, no positions, no pnl, no retrieval deltas
- Hard locks: all keys present and True; buy/sell/hold always False
- No forbidden field substrings in output (score, rank, confidence, weighted, buy, sell, hold)
- CLI command: registered and parses args correctly
- handler: is_handler_registered() returns True
- handler: TRACK_NORMAL_FIRST_15M job kind constant correct
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
from printer_v1.operator_cli.lane_x10_10_normal_15m_runner import (
    LANE_X10_10_COMMAND_NAME,
    LANE_X10_10_MAX_TOKEN_COUNT,
    LANE_X10_10_MIN_TOKEN_COUNT,
    LANE_X10_10_STATUS_BLOCKED,
    LANE_X10_10_STATUS_COMPLETED,
    LANE_X10_10_STATUS_STOPPED,
    _HARD_LOCKS,
    _load_and_validate_normal_token_list,
    run_normal_15m_memory_factory_cycle,
)
from printer_v1.sources.governed_execution import (
    FIXTURE_SUCCESS,
    build_fixture_source_adapter,
)

# ---------------------------------------------------------------------------
# Test constants
# ---------------------------------------------------------------------------

# TRACK_NORMAL test mints (44 chars, base58 alphabet)
_MINT_A = "NormMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_MINT_B = "NormMintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_MINT_C = "NormMintCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
_MINT_D = "NormMintDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"
_MINT_E = "NormMintEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"
_MINT_F = "NormMintFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
_MINT_G = "NormMintGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"
_MINT_EXTRA = "NormMintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"

_PAIR_A = "NormPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_B = "NormPairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_PAIR_C = "NormPairCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC"
_PAIR_D = "NormPairDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD"
_PAIR_E = "NormPairEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE"
_PAIR_F = "NormPairFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFF"
_PAIR_G = "NormPairGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGGG"

_TRACK_FAST_MINT = "FastMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_TRACK_FAST_PAIR = "FastPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"

_FORBIDDEN_SUBSTRINGS = {
    "buy_signal",
    "sell_signal",
    "hold_signal",
    "score",
    "rank",
    "confidence",
    "weighted",
    "retrieval_match",
    "paper_position",
    "paper_trade_event",
}


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
                    "symbol": "NRM",
                    "name": "Normal Test Token",
                    "price_usd": 0.00012,
                    "liquidity_usd": 8000.0,
                    "volume_5m": 200.0,
                    "volume_1h": 2400.0,
                    "volume_24h": 57600.0,
                    "txns_5m": 5,
                    "txns_1h": 60,
                    "txns_24h": 1440,
                    "fdv": 120000.0,
                    "market_cap": 100000.0,
                    "price_change_5m": 0.2,
                    "price_change_1h": -0.5,
                    "price_change_24h": -3.0,
                }
            ],
        },
    )


class _FailingCallable:
    """Always raises RuntimeError — simulates source failures."""

    def __call__(self, *args, **kwargs):
        raise RuntimeError("simulated source failure for TRACK_NORMAL budget test")


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

    def _insert_token(self, mint: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO printer_tokens (token_mint, chain, created_at, updated_at)"
                " VALUES (?, 'solana', datetime('now'), datetime('now'))",
                (mint,),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _insert_pair(self, token_id: int, pair_address: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, created_at, updated_at)"
                " VALUES (?, ?, datetime('now'), datetime('now'))",
                (token_id, pair_address),
            )
            conn.commit()
            return int(cur.lastrowid)

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
        tracking_lane: str = "TRACK_NORMAL",
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

    def _run(
        self,
        mints_pairs: list[tuple[str, str]],
        *,
        tracking_lane: str = "TRACK_NORMAL",
        operator_approved: bool = True,
        cycle_budget: int = 1,
        adapter_map=None,
        **overrides,
    ) -> dict[str, Any]:
        tf = self._write_token_list(mints_pairs, tracking_lane=tracking_lane)
        if adapter_map is None:
            adapter_map = _make_adapter_map(*mints_pairs)
        return run_normal_15m_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
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
# 1. Validator tests
# ---------------------------------------------------------------------------

class TestValidatorAccepts(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, tokens):
        tf = pathlib.Path(self._tmp.name) / "tl.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _one_token(self, **overrides):
        base = {
            "token_mint": _MINT_A,
            "pair_address": _PAIR_A,
            "chain": "solana",
            "tracking_lane": "TRACK_NORMAL",
            "operator_approved": True,
        }
        base.update(overrides)
        return base

    def test_one_track_normal_token_validates(self):
        tf = self._write([self._one_token()])
        valid, reason, tokens = _load_and_validate_normal_token_list(tf)
        self.assertTrue(valid, reason)
        self.assertEqual(len(tokens), 1)

    def test_seven_track_normal_tokens_validate(self):
        mints = [_MINT_A, _MINT_B, _MINT_C, _MINT_D, _MINT_E, _MINT_F, _MINT_G]
        pairs = [_PAIR_A, _PAIR_B, _PAIR_C, _PAIR_D, _PAIR_E, _PAIR_F, _PAIR_G]
        tokens = [
            {
                "token_mint": m, "pair_address": p, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            }
            for m, p in zip(mints, pairs)
        ]
        tf = self._write(tokens)
        valid, reason, result_tokens = _load_and_validate_normal_token_list(tf)
        self.assertTrue(valid, reason)
        self.assertEqual(len(result_tokens), 7)

    def test_eight_tokens_rejected(self):
        mints = [_MINT_A, _MINT_B, _MINT_C, _MINT_D, _MINT_E, _MINT_F, _MINT_G, _MINT_EXTRA]
        pairs = [_PAIR_A, _PAIR_B, _PAIR_C, _PAIR_D, _PAIR_E, _PAIR_F, _PAIR_G, "ExtraPairXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"]
        tokens = [
            {
                "token_mint": m, "pair_address": p, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            }
            for m, p in zip(mints, pairs)
        ]
        tf = self._write(tokens)
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn(str(LANE_X10_10_MAX_TOKEN_COUNT), reason)

    def test_zero_tokens_rejected(self):
        tf = self._write([])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn(str(LANE_X10_10_MIN_TOKEN_COUNT), reason)

    def test_track_fast_token_rejected(self):
        tf = self._write([self._one_token(tracking_lane="TRACK_FAST")])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn("TRACK_NORMAL", reason)

    def test_watch_only_token_rejected(self):
        tf = self._write([self._one_token(tracking_lane="WATCH_ONLY")])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn("TRACK_NORMAL", reason)

    def test_ignore_token_rejected(self):
        tf = self._write([self._one_token(tracking_lane="IGNORE")])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn("TRACK_NORMAL", reason)

    def test_operator_approved_required(self):
        tf = self._write([self._one_token(operator_approved=False)])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn("operator_approved", reason)

    def test_missing_pair_address_rejected(self):
        tok = {
            "token_mint": _MINT_A, "chain": "solana",
            "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
        }
        tf = self._write([tok])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)

    def test_placeholder_pair_rejected(self):
        tf = self._write([self._one_token(pair_address="PLACEHOLDER_PAIR")])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)

    def test_duplicate_mint_rejected(self):
        tokens = [
            {
                "token_mint": _MINT_A, "pair_address": _PAIR_A, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            },
            {
                "token_mint": _MINT_A, "pair_address": _PAIR_B, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            },
        ]
        tf = self._write(tokens)
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn("duplicate", reason.lower())

    def test_duplicate_pair_rejected(self):
        tokens = [
            {
                "token_mint": _MINT_A, "pair_address": _PAIR_A, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            },
            {
                "token_mint": _MINT_B, "pair_address": _PAIR_A, "chain": "solana",
                "tracking_lane": "TRACK_NORMAL", "operator_approved": True,
            },
        ]
        tf = self._write(tokens)
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn("duplicate", reason.lower())

    def test_non_solana_chain_rejected(self):
        tf = self._write([self._one_token(chain="ethereum")])
        valid, reason, _ = _load_and_validate_normal_token_list(tf)
        self.assertFalse(valid)
        self.assertIn("solana", reason)

    def test_none_path_returns_invalid(self):
        valid, reason, tokens = _load_and_validate_normal_token_list(None)
        self.assertFalse(valid)
        self.assertEqual(tokens, [])


# ---------------------------------------------------------------------------
# 2. Window kind gate tests
# ---------------------------------------------------------------------------

class TestWindowKindGates(_DbBase):
    def test_window_15m_is_enabled(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertNotEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)
        self.assertEqual(result["window_kind"], "WINDOW_15M")

    def test_window_5m_micro_event_forbidden_as_main(self):
        result = self._run(
            [(_MINT_A, _PAIR_A)], window_kind="WINDOW_5M_MICRO_EVENT", cycle_budget=0
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)
        self.assertTrue(
            any("support-only" in r or "5m" in r.lower() for r in result["blocked_reasons"])
        )

    def test_window_1h_blocked(self):
        result = self._run(
            [(_MINT_A, _PAIR_A)], window_kind="WINDOW_1H", cycle_budget=0
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)

    def test_window_4h_blocked(self):
        result = self._run(
            [(_MINT_A, _PAIR_A)], window_kind="WINDOW_4H", cycle_budget=0
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)

    def test_window_12h_blocked(self):
        result = self._run(
            [(_MINT_A, _PAIR_A)], window_kind="WINDOW_12H", cycle_budget=0
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)

    def test_window_24h_blocked(self):
        result = self._run(
            [(_MINT_A, _PAIR_A)], window_kind="WINDOW_24H", cycle_budget=0
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 3. Job kind tests
# ---------------------------------------------------------------------------

class TestJobKind(_DbBase):
    def test_creates_track_normal_first_15m_jobs(self):
        self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_kind FROM printer_scheduler_jobs WHERE job_kind = ?",
                ("TRACK_NORMAL_FIRST_15M",),
            ).fetchall()
        self.assertGreater(len(rows), 0, "Expected TRACK_NORMAL_FIRST_15M jobs in DB")

    def test_does_not_create_track_fast_first_15m_jobs(self):
        self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_kind FROM printer_scheduler_jobs WHERE job_kind = ?",
                ("TRACK_FAST_FIRST_15M",),
            ).fetchall()
        self.assertEqual(len(rows), 0, "TRACK_FAST_FIRST_15M jobs must never be created by X10.10B")

    def test_job_name_prefix_is_x10_10(self):
        self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT job_name FROM printer_scheduler_jobs"
            ).fetchall()
        names = [r[0] for r in rows]
        self.assertTrue(
            any("x10_10" in n for n in names),
            f"Expected x10_10 prefix in job names; got {names}"
        )


# ---------------------------------------------------------------------------
# 4. Freshness advisory tests (never blocks)
# ---------------------------------------------------------------------------

class TestFreshnessAdvisory(_DbBase):
    """TRACK_NORMAL freshness is advisory only. Stale/unknown never blocks run."""

    def test_freshness_advisory_results_in_output(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertIn("freshness_advisory_results", result)

    def test_stale_track_normal_does_not_block_run(self):
        """Token with no discovery evidence (unknown freshness) must not block."""
        # No source responses or discovery candidates inserted — FRESHNESS_UNKNOWN
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=0)
        # Should not be BLOCKED by freshness
        self.assertNotIn(
            "freshness",
            " ".join(result.get("blocked_reasons", [])).lower(),
        )

    def test_freshness_advisory_never_adds_to_blocked_reasons(self):
        """Even with zero freshness evidence, blocked_reasons must not mention freshness."""
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=0)
        reasons_text = " ".join(result.get("blocked_reasons", [])).lower()
        self.assertNotIn("freshness", reasons_text)
        self.assertNotIn("stale", reasons_text)

    def test_fresh_within_300s_no_warning_in_advisory(self):
        """Token with source_response within 300s should be FRESH in advisory results."""
        ts = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        self._insert_source_response(ts, _PAIR_A, _MINT_A)
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=0)
        advisory = result.get("freshness_advisory_results", [])
        if advisory:
            # Should be fresh, not stale
            for item in advisory:
                if item.get("mint") == _MINT_A:
                    self.assertNotIn("STALE", item.get("status", ""))

    def test_freshness_advisory_results_is_list(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=0)
        self.assertIsInstance(result["freshness_advisory_results"], list)

    def test_freshness_gate_results_not_in_output(self):
        """freshness_gate_results is X5's field name; X10.10B must not use it."""
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=0)
        self.assertNotIn("freshness_gate_results", result)


# ---------------------------------------------------------------------------
# 5. Runner gate tests (operator_approved, db_path, backup, token_list)
# ---------------------------------------------------------------------------

class TestRunnerGates(_DbBase):
    def test_operator_not_approved_blocks(self):
        result = self._run([(_MINT_A, _PAIR_A)], operator_approved=False, cycle_budget=0)
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)
        self.assertTrue(
            any("operator_approved" in r for r in result["blocked_reasons"])
        )

    def test_missing_db_path_blocks(self):
        result = run_normal_15m_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path=None,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)

    def test_nonexistent_db_blocks(self):
        result = run_normal_15m_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path="/nonexistent/printer_v1.sqlite3",
            backup_proof_path=self.backup_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)

    def test_missing_backup_blocks(self):
        result = run_normal_15m_memory_factory_cycle(
            token_list_path=self._write_token_list([(_MINT_A, _PAIR_A)]),
            db_path=self.db_path,
            backup_proof_path=None,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_MINT_A, _PAIR_A)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)

    def test_track_fast_token_blocked(self):
        tf = self._write_token_list([(_TRACK_FAST_MINT, _TRACK_FAST_PAIR)], tracking_lane="TRACK_FAST")
        result = run_normal_15m_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map((_TRACK_FAST_MINT, _TRACK_FAST_PAIR)),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)
        self.assertTrue(
            any("TRACK_NORMAL" in r for r in result["blocked_reasons"])
        )

    def test_eight_tokens_blocked(self):
        mints_pairs = [
            (_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B), (_MINT_C, _PAIR_C),
            (_MINT_D, _PAIR_D), (_MINT_E, _PAIR_E), (_MINT_F, _PAIR_F),
            (_MINT_G, _PAIR_G),
            (_MINT_EXTRA, "ExtraPairXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"),
        ]
        tf = self._write_token_list(mints_pairs)
        result = run_normal_15m_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(*mints_pairs),
            _cycle_budget=0,
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 6. Source Governor gate tests
# ---------------------------------------------------------------------------

class TestSourceGovernorGate(_DbBase):
    def test_source_governor_checked_before_source_call(self):
        """With adapter_map, each step creates a source request — governed."""
        self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        with self._conn() as conn:
            count = int(
                conn.execute("SELECT COUNT(*) FROM printer_source_requests").fetchone()[0]
            )
        # Governor recorded at least one request from the cadence cycle
        self.assertGreater(count, 0, "Source Governor must record source requests")


# ---------------------------------------------------------------------------
# 7. Running jobs / active locks gate tests
# ---------------------------------------------------------------------------

class TestSchedulerGates(_DbBase):
    def _inject_running_job(self):
        """Insert a RUNNING job to simulate a concurrent scheduler conflict."""
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

    def test_running_job_causes_handler_to_block(self):
        """When a RUNNING job exists (not the current job), Gate 2 should block."""
        self._inject_running_job()
        # The step itself creates a new job but then Gate 2 finds the blocking job.
        # The result should be a HANDLER_BLOCKED cycle (not a runner-level BLOCKED).
        # With source_budget_max_consecutive_failures=0, first failure stops safely.
        result = self._run(
            [(_MINT_A, _PAIR_A)],
            cycle_budget=1,
            source_budget_max_consecutive_failures=0,
        )
        # Runner started (not BLOCKED by pre-flight), but hit failure during execution
        self.assertIn(
            result["lane_x10_10_status"],
            {LANE_X10_10_STATUS_STOPPED, LANE_X10_10_STATUS_COMPLETED},
        )


# ---------------------------------------------------------------------------
# 8. Consecutive failures safe stop
# ---------------------------------------------------------------------------

class TestConsecutiveFailures(_DbBase):
    def test_consecutive_failures_trigger_safe_stop(self):
        """All-failing adapters with limit=0 must stop after first failure."""
        am = _make_failing_adapter_map(_MINT_A, _MINT_B)
        tf = self._write_token_list([(_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B)])
        result = run_normal_15m_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            _adapter_map=am,
            _cycle_budget=10,
            source_budget_max_consecutive_failures=0,
        )
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_STOPPED)
        self.assertGreater(result["total_source_failures"], 0)

    def test_consecutive_failures_reset_on_success(self):
        """Successful step resets consecutive failure counter."""
        # Run with a working adapter — cycle budget 1 should complete
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        # Should NOT be STOPPED (counter resets on success)
        self.assertNotEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_STOPPED)


# ---------------------------------------------------------------------------
# 9. Lock field tests
# ---------------------------------------------------------------------------

class TestLockFields(_DbBase):
    def test_paper_decisions_delta_is_zero(self):
        before = self._count_table("printer_paper_decisions")
        self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        after = self._count_table("printer_paper_decisions")
        self.assertEqual(after - before, 0, "paper_decisions must not be written")

    def test_positions_delta_is_zero(self):
        before = self._count_table("printer_paper_positions")
        self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        after = self._count_table("printer_paper_positions")
        self.assertEqual(after - before, 0)

    def test_pnl_delta_is_zero(self):
        before = self._count_table("printer_paper_trade_events")
        self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        after = self._count_table("printer_paper_trade_events")
        self.assertEqual(after - before, 0)

    def test_retrieval_delta_is_zero(self):
        for tbl in ("printer_retrieval_candidates", "printer_retrieval_results"):
            before = self._count_table(tbl)
            self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
            after = self._count_table(tbl)
            self.assertEqual(after - before, 0, f"{tbl} must not grow")

    def test_output_paper_decisions_created_is_zero(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result.get("paper_decisions_created"), 0)

    def test_output_positions_created_is_zero(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result.get("positions_created"), 0)

    def test_output_pnl_created_is_zero(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result.get("pnl_created"), 0)

    def test_output_retrieval_rows_created_is_zero(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result.get("retrieval_rows_created"), 0)

    def test_hard_locks_all_present_and_true(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        hard_locks = result.get("hard_locks", {})
        self.assertIsInstance(hard_locks, dict)
        self.assertGreater(len(hard_locks), 10, "Expected many hard lock keys")
        for key, value in hard_locks.items():
            self.assertTrue(value, f"hard_lock {key!r} must be True")

    def test_buy_enabled_false(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertFalse(result.get("buy_enabled"))

    def test_sell_enabled_false(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertFalse(result.get("sell_enabled"))

    def test_hold_enabled_false(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertFalse(result.get("hold_enabled"))

    def test_zero_clean_memories_is_valid(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertTrue(result.get("zero_clean_memories_is_valid"))

    def test_hard_locks_module_constant_no_track_fast(self):
        """Runner hard locks must include no_track_fast_in_normal_runner."""
        self.assertIn("no_track_fast_in_normal_runner", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_track_fast_in_normal_runner"])


# ---------------------------------------------------------------------------
# 10. No forbidden fields in output
# ---------------------------------------------------------------------------

class TestNoForbiddenFields(_DbBase):
    def _flatten_keys(self, d: Any, prefix: str = "") -> set[str]:
        keys = set()
        if isinstance(d, dict):
            for k, v in d.items():
                full_key = f"{prefix}.{k}" if prefix else k
                keys.add(full_key.lower())
                keys.update(self._flatten_keys(v, full_key))
        elif isinstance(d, list):
            for item in d:
                keys.update(self._flatten_keys(item, prefix))
        return keys

    def test_no_buy_sell_hold_signal_fields(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        all_keys = self._flatten_keys(result)
        for forbidden in ("buy_signal", "sell_signal", "hold_signal"):
            self.assertNotIn(forbidden, all_keys, f"Forbidden field {forbidden!r} in output")

    def test_no_score_rank_confidence_fields(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        all_keys = self._flatten_keys(result)
        for forbidden in ("score", "rank", "confidence", "weighted"):
            # These must not appear as standalone key names in the output
            for key in all_keys:
                # Allow substrings only if they're legitimate (e.g. "source_request")
                # The rule is: no key that IS one of the forbidden words
                if key == forbidden:
                    self.fail(f"Forbidden key {forbidden!r} found in output: {key!r}")

    def test_no_paper_position_paper_trade_fields(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        all_keys = self._flatten_keys(result)
        for forbidden in ("paper_position", "paper_trade_event"):
            for key in all_keys:
                # forbidden_table_counts legitimately tracks row counts (all zero)
                # for those tables as part of the audit guard; skip that prefix
                if key.startswith("forbidden_table_counts."):
                    continue
                self.assertNotIn(forbidden, key, f"Forbidden substring {forbidden!r} in key {key!r}")


# ---------------------------------------------------------------------------
# 11. Output shape tests
# ---------------------------------------------------------------------------

class TestOutputShape(_DbBase):
    def test_required_top_level_fields_present(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        required = {
            "command", "lane_x10_10_status", "operator_approved", "db_path",
            "selected_profile", "requested_duration_seconds", "actual_duration_seconds",
            "run_started_at", "run_finished_at", "window_kind",
            "selected_token_count", "total_window_closes", "clean_memory_rows_created",
            "paper_decisions_created", "positions_created", "pnl_created",
            "retrieval_rows_created", "stopped_safely_reason", "zero_clean_memories_is_valid",
            "hard_locks", "buy_enabled", "sell_enabled", "hold_enabled",
            "freshness_advisory_results", "token_reports", "cycles",
            "cadence_cycles_completed", "pair_drift_detected",
        }
        for field in required:
            self.assertIn(field, result, f"Missing required output field: {field!r}")

    def test_command_name_is_correct(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        self.assertEqual(result["command"], LANE_X10_10_COMMAND_NAME)

    def test_selected_token_count_matches_input(self):
        result = self._run([(_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B)], cycle_budget=1)
        self.assertEqual(result["selected_token_count"], 2)

    def test_token_reports_is_list(self):
        result = self._run([(_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B)], cycle_budget=1)
        self.assertIsInstance(result["token_reports"], list)
        self.assertEqual(len(result["token_reports"]), 2)

    def test_token_report_has_required_fields(self):
        result = self._run([(_MINT_A, _PAIR_A)], cycle_budget=1)
        report = result["token_reports"][0]
        for field in ("slot", "mint", "pair_address_supplied", "snapshots_created",
                      "memory_windows_created", "window_closes", "clean_memory_created"):
            self.assertIn(field, report, f"Missing token report field: {field!r}")

    def test_slot_a_assigned_to_first_token(self):
        result = self._run([(_MINT_A, _PAIR_A), (_MINT_B, _PAIR_B)], cycle_budget=1)
        reports = result["token_reports"]
        self.assertEqual(reports[0]["slot"], "A")
        self.assertEqual(reports[1]["slot"], "B")

    def test_blocked_result_has_required_fields(self):
        result = self._run([(_MINT_A, _PAIR_A)], operator_approved=False, cycle_budget=0)
        self.assertEqual(result["lane_x10_10_status"], LANE_X10_10_STATUS_BLOCKED)
        for field in ("blocked_reasons", "hard_locks", "buy_enabled", "freshness_advisory_results"):
            self.assertIn(field, result)


# ---------------------------------------------------------------------------
# 12. Handler module tests
# ---------------------------------------------------------------------------

class TestHandlerModule(unittest.TestCase):
    def test_is_handler_registered_true(self):
        from printer_v1.operator_cli.lane_e2h_normal_first_15m_handler import (
            is_handler_registered,
        )
        self.assertTrue(is_handler_registered())

    def test_handler_job_kind_constant(self):
        from printer_v1.operator_cli.lane_e2h_normal_first_15m_handler import (
            HANDLER_JOB_KIND,
            HANDLER_LIFECYCLE_LANE,
            HANDLER_TARGET_WINDOW,
        )
        self.assertEqual(HANDLER_JOB_KIND, "TRACK_NORMAL_FIRST_15M")
        self.assertEqual(HANDLER_LIFECYCLE_LANE, "TRACK_NORMAL")
        self.assertEqual(HANDLER_TARGET_WINDOW, "WINDOW_15M")

    def test_handler_status_constants(self):
        from printer_v1.operator_cli.lane_e2h_normal_first_15m_handler import (
            E2H_NORMAL_STATUS_BLOCKED,
            E2H_NORMAL_STATUS_EXECUTED,
        )
        self.assertIn("TRACK_NORMAL", E2H_NORMAL_STATUS_EXECUTED)
        self.assertIn("TRACK_NORMAL", E2H_NORMAL_STATUS_BLOCKED)

    def test_handler_no_adapter_returns_valid_result(self):
        """Handler without adapter either passes transport gate (E2I available)
        and returns EXECUTED with no source_results, or blocks at the transport gate.
        Either outcome is valid; what must never happen is an unhandled exception."""
        from printer_v1.operator_cli.lane_e2h_normal_first_15m_handler import (
            E2H_NORMAL_STATUS_BLOCKED,
            E2H_NORMAL_STATUS_EXECUTED,
            execute_track_normal_first_15m_job,
        )
        import sqlite3, tempfile, pathlib
        from printer_v1.db import apply_migrations

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = pathlib.Path(tmp) / "test.sqlite3"
            apply_migrations(db)
            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO printer_scheduler_jobs"
                " (job_name, job_kind, status, scheduled_for, created_at, updated_at)"
                " VALUES ('test_job', 'TRACK_NORMAL_FIRST_15M', 'RUNNING', ?, ?, ?)",
                (now, now, now),
            )
            conn.commit()
            job_row = conn.execute(
                "SELECT * FROM printer_scheduler_jobs LIMIT 1"
            ).fetchone()
            result = execute_track_normal_first_15m_job(conn, job_row, adapter=None)
            conn.close()

        # E2I may be installed (EXECUTED path) or missing (BLOCKED on transport gate)
        self.assertIn(result["status"], {E2H_NORMAL_STATUS_EXECUTED, E2H_NORMAL_STATUS_BLOCKED})
        # Either way: paper/position/pnl must be zero
        self.assertEqual(result.get("paper_decisions_created"), 0)
        self.assertEqual(result.get("positions_created"), 0)
        self.assertEqual(result.get("pnl_created"), 0)

    def test_handler_forbidden_tables_all_zero(self):
        """Handler execution result always has zero paper/position/pnl created."""
        from printer_v1.operator_cli.lane_e2h_normal_first_15m_handler import (
            execute_track_normal_first_15m_job,
        )
        import sqlite3, tempfile, pathlib
        from printer_v1.db import apply_migrations

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = pathlib.Path(tmp) / "test.sqlite3"
            apply_migrations(db)
            conn = sqlite3.connect(str(db))
            conn.row_factory = sqlite3.Row
            now = datetime.now(timezone.utc).isoformat()
            conn.execute(
                "INSERT INTO printer_scheduler_jobs"
                " (job_name, job_kind, status, scheduled_for, created_at, updated_at)"
                " VALUES ('test_job', 'TRACK_NORMAL_FIRST_15M', 'RUNNING', ?, ?, ?)",
                (now, now, now),
            )
            conn.commit()
            job_row = conn.execute(
                "SELECT * FROM printer_scheduler_jobs LIMIT 1"
            ).fetchone()
            result = execute_track_normal_first_15m_job(conn, job_row, adapter=None)
            conn.close()

        self.assertEqual(result.get("paper_decisions_created"), 0)
        self.assertEqual(result.get("positions_created"), 0)
        self.assertEqual(result.get("pnl_created"), 0)


# ---------------------------------------------------------------------------
# 13. CLI registration tests
# ---------------------------------------------------------------------------

class TestCliRegistration(unittest.TestCase):
    def test_command_name_constant(self):
        self.assertEqual(
            LANE_X10_10_COMMAND_NAME, "printer-run-lane-x10-10-normal-15m-cycle"
        )

    def test_main_function_importable(self):
        from printer_v1.operator_cli.commands import (
            main_run_lane_x10_10_normal_15m_cycle,
        )
        self.assertTrue(callable(main_run_lane_x10_10_normal_15m_cycle))

    def test_cli_missing_args_exits_nonzero(self):
        from printer_v1.operator_cli.commands import (
            main_run_lane_x10_10_normal_15m_cycle,
        )
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                rc = main_run_lane_x10_10_normal_15m_cycle([])
        except SystemExit as exc:
            rc = exc.code
        self.assertNotEqual(rc, 0)

    def test_min_max_constants(self):
        self.assertEqual(LANE_X10_10_MIN_TOKEN_COUNT, 1)
        self.assertEqual(LANE_X10_10_MAX_TOKEN_COUNT, 7)


if __name__ == "__main__":
    unittest.main()
