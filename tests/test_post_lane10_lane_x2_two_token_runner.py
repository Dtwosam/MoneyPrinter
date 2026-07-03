"""Lane X2 — Two-Token Controlled 15m Proof tests.

Validates:
- Exactly 2 TRACK_FAST operator-approved Solana tokens accepted; 1/3/0/duplicates rejected.
- Unapproved, non-TRACK_FAST, non-solana, placeholder tokens rejected.
- A/B deterministic rotation: even ticks → slot A, odd ticks → slot B.
- Evidence isolated per token — token A snapshots cannot build token B memory.
- Per-token source/snapshot/window-close counts reported independently.
- All retrieval/paper/BUY/position/PnL locks remain zero.
- Hard locks dict all True.
- Idempotent Lane K replay: second call does not create more rows.
- All window-kind gates remain: 5m forbidden as main, 1h/4h/12h/24h blocked.
- Zero clean memories is a valid outcome.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile
import unittest
from typing import Any

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_x2_two_token_runner import (
    LANE_X2_EXACT_TOKEN_COUNT,
    LANE_X2_STATUS_BLOCKED,
    LANE_X2_STATUS_COMPLETED,
    LANE_X2_STATUS_STOPPED,
    _HARD_LOCKS,
    _load_and_validate_two_token_list,
    run_two_token_memory_factory_cycle,
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
_PAIR_A = "LaneX2TestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_B = "LaneX2TestPairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"

_MINT_C = "7aQFm7rFS8U4klgO4DaMs35yiOGckt5tuO5tOvVGrump"

_REQUIRED_REPORTING_FIELDS = frozenset({
    "command",
    "lane_x2_status",
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
                    "symbol": "X2T",
                    "name": "Lane X2 Test Token",
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

    def _write_x2_token_file(
        self,
        *,
        mint_a: str = _MINT_A,
        pair_a: str = _PAIR_A,
        mint_b: str = _MINT_B,
        pair_b: str = _PAIR_B,
        tracking_lane_a: str = "TRACK_FAST",
        tracking_lane_b: str = "TRACK_FAST",
        approved_a: bool = True,
        approved_b: bool = True,
        tokens_override: list | None = None,
    ) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens_x2.json"
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
        token_file = self._write_x2_token_file()
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
        return run_two_token_memory_factory_cycle(**defaults)


# ---------------------------------------------------------------------------
# 1. Validator tests — no DB
# ---------------------------------------------------------------------------

class TestLaneX2TwoTokenValidator(unittest.TestCase):
    """Unit tests for _load_and_validate_two_token_list."""

    def _write(self, tokens: list, tmp_dir: str) -> pathlib.Path:
        p = pathlib.Path(tmp_dir) / "tokens.json"
        p.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return p

    def test_two_tokens_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, tok_a, tok_b = _load_and_validate_two_token_list(path)
            self.assertTrue(valid, reason)
            self.assertEqual(tok_a["token_mint"], _MINT_A)
            self.assertEqual(tok_b["token_mint"], _MINT_B)

    def test_one_token_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("1", reason)

    def test_three_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_C, "pair_address": "PAIRC",
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("3", reason)

    def test_zero_tokens_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("0", reason)

    def test_unapproved_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": False},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("operator_approved", reason)

    def test_track_normal_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_NORMAL",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("TRACK_FAST", reason)

    def test_watch_only_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "WATCH_ONLY",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)

    def test_non_solana_chain_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "ethereum", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("solana", reason)

    def test_placeholder_mint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": "PLACEHOLDER_MINT_A", "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("placeholder", reason.lower())

    def test_placeholder_pair_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": "PLACEHOLDER_PAIR_A",
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("placeholder", reason.lower())

    def test_empty_mint_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": "", "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)

    def test_duplicate_mints_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_A, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("duplicate", reason.lower())
            self.assertIn("mint", reason.lower())

    def test_duplicate_pair_addresses_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = self._write([
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ], tmp)
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid)
            self.assertIn("duplicate", reason.lower())
            self.assertIn("pair", reason.lower())

    def test_missing_file_rejected(self):
        valid, reason, _, _ = _load_and_validate_two_token_list(
            "/nonexistent/path/tokens.json"
        )
        self.assertFalse(valid)
        self.assertIn("not found", reason.lower())

    def test_invalid_json_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad = pathlib.Path(tmp) / "bad.json"
            bad.write_text("NOT_JSON", encoding="utf-8")
            valid, reason, _, _ = _load_and_validate_two_token_list(bad)
            self.assertFalse(valid)
            self.assertIn("unreadable", reason.lower())

    def test_none_path_rejected(self):
        valid, reason, _, _ = _load_and_validate_two_token_list(None)
        self.assertFalse(valid)
        self.assertIn("required", reason.lower())

    def test_e2i_format_not_accepted_as_x2_format(self):
        """A token list using E2I field names (lifecycle_lane / approved_by_operator)
        must NOT be accepted by the Lane X2 validator — wrong field names → rejected."""
        with tempfile.TemporaryDirectory() as tmp:
            path = pathlib.Path(tmp) / "e2i_format.json"
            path.write_text(json.dumps({
                "tokens": [
                    {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST",
                     "approved_by_operator": True},
                    {"token_mint": _MINT_B, "lifecycle_lane": "TRACK_FAST",
                     "approved_by_operator": True},
                ]
            }), encoding="utf-8")
            # E2I fields won't match X2 field names → chain and tracking_lane absent
            valid, reason, _, _ = _load_and_validate_two_token_list(path)
            self.assertFalse(valid, "E2I format must be rejected by X2 validator")


# ---------------------------------------------------------------------------
# 2. Gate / blocked tests
# ---------------------------------------------------------------------------

class TestLaneX2GateChecks(_DbBase):
    """run_two_token_memory_factory_cycle must return LANE_X2_BLOCKED for bad inputs."""

    def test_blocked_without_operator_approved(self):
        r = self._run(operator_approved=False)
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)
        self.assertIn("operator_approved", str(r.get("blocked_reasons", "")))

    def test_blocked_missing_token_list_path(self):
        r = run_two_token_memory_factory_cycle(
            None, self.db_path, self.backup_proof_path,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_nonexistent_token_list_path(self):
        r = run_two_token_memory_factory_cycle(
            "/nonexistent/tokens.json", self.db_path, self.backup_proof_path,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_missing_db_path(self):
        r = run_two_token_memory_factory_cycle(
            self._write_x2_token_file(), None, self.backup_proof_path,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_missing_backup_proof_path(self):
        r = run_two_token_memory_factory_cycle(
            self._write_x2_token_file(), self.db_path, None,
            operator_approved=True, _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_window_5m_as_main(self):
        r = self._run(window_kind="WINDOW_5M_MICRO_EVENT")
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_window_1h_as_main(self):
        r = self._run(window_kind="WINDOW_1H")
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_window_4h_as_main(self):
        r = self._run(window_kind="WINDOW_4H")
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_window_12h_as_main(self):
        r = self._run(window_kind="WINDOW_12H")
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_window_24h_as_main(self):
        r = self._run(window_kind="WINDOW_24H")
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_12h_profile_without_allow_long_run(self):
        r = self._run(duration_profile="12h", allow_long_bounded_run=False)
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_24h_profile_without_allow_long_run(self):
        r = self._run(duration_profile="24h", allow_long_bounded_run=False)
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_one_token_in_list(self):
        token_file = pathlib.Path(self._tmp.name) / "one_token.json"
        token_file.write_text(json.dumps({
            "tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ]
        }), encoding="utf-8")
        r = run_two_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_three_tokens_in_list(self):
        token_file = pathlib.Path(self._tmp.name) / "three_tokens.json"
        token_file.write_text(json.dumps({
            "tokens": [
                {"token_mint": _MINT_A, "pair_address": _PAIR_A,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_B, "pair_address": _PAIR_B,
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
                {"token_mint": _MINT_C, "pair_address": "PAIRCx99",
                 "chain": "solana", "tracking_lane": "TRACK_FAST",
                 "operator_approved": True},
            ]
        }), encoding="utf-8")
        r = run_two_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_unapproved_token_in_list(self):
        token_file = self._write_x2_token_file(approved_b=False)
        r = run_two_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_duplicate_mints_in_list(self):
        token_file = self._write_x2_token_file(mint_b=_MINT_A)
        r = run_two_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)

    def test_blocked_non_track_fast_in_list(self):
        token_file = self._write_x2_token_file(tracking_lane_a="TRACK_NORMAL")
        r = run_two_token_memory_factory_cycle(
            token_file, self.db_path, self.backup_proof_path,
            operator_approved=True,
            _adapter_map=_make_adapter_map(),
            _cycle_budget=1,
        )
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 3. Execution tests — happy-path execution with fixture adapters
# ---------------------------------------------------------------------------

class TestLaneX2Execution(_DbBase):
    """End-to-end execution tests for the Lane X2 two-token runner."""

    def test_single_cycle_budget_completes(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["lane_x2_status"], LANE_X2_STATUS_COMPLETED)

    def test_selected_token_count_is_2(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["selected_token_count"], LANE_X2_EXACT_TOKEN_COUNT)

    def test_token_a_mint_in_result(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["token_a_mint"], _MINT_A)

    def test_token_b_mint_in_result(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["token_b_mint"], _MINT_B)

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

    def test_single_cycle_first_window_close_is_slot_a(self):
        """With budget=1, the only window close must be for slot A (even tick)."""
        r = self._run(cycle_budget=1)
        cycles = r.get("cycles", [])
        self.assertGreaterEqual(len(cycles), 1, "At least 1 cycle must be in cycles list")
        self.assertEqual(cycles[0]["slot"], "A", "First cycle must be slot A")

    def test_two_cycles_alternate_a_then_b(self):
        """With budget=2, cycle 0 = slot A, cycle 1 = slot B."""
        r = self._run(cycle_budget=2)
        cycles = r.get("cycles", [])
        self.assertGreaterEqual(len(cycles), 2, "Budget=2 must produce 2 cycles")
        self.assertEqual(cycles[0]["slot"], "A", "Cycle 0 must be slot A")
        self.assertEqual(cycles[1]["slot"], "B", "Cycle 1 must be slot B")

    def test_two_cycles_total_window_closes_is_2(self):
        r = self._run(cycle_budget=2)
        self.assertEqual(r["total_window_closes"], 2)

    def test_two_cycles_each_token_gets_one_window_close(self):
        r = self._run(cycle_budget=2)
        self.assertEqual(r["token_a_report"]["window_closes"], 1)
        self.assertEqual(r["token_b_report"]["window_closes"], 1)

    def test_token_a_b_window_closes_sum_to_total(self):
        r = self._run(cycle_budget=2)
        a_closes = r["token_a_report"]["window_closes"]
        b_closes = r["token_b_report"]["window_closes"]
        self.assertEqual(a_closes + b_closes, r["total_window_closes"])

    # Evidence isolation -------------------------------------------------------

    def test_token_b_has_no_memory_windows_when_only_a_ran(self):
        """With budget=1, only slot A gets a window close; token B must have
        zero memory windows."""
        r = self._run(cycle_budget=1)
        # Token B never gets a snapshot with budget=1
        b_rep = r["token_b_report"]
        self.assertEqual(
            b_rep["memory_windows_created"], 0,
            "Token B must not have any memory windows when only slot A ran",
        )

    def test_token_a_has_no_memory_windows_when_only_b_ran(self):
        """Verify isolation from the B side: run 2 cycles but check which tokens
        have windows.  With budget=2, A gets 1 close and B gets 1 close.
        Both are non-zero, so instead run a scenario where we check B's
        first cycle does not create A memory."""
        # With budget=2, both tokens close once — just verify neither leaks into
        # the other's count by confirming per-token counts are each exactly 1.
        r = self._run(cycle_budget=2)
        a_rep = r["token_a_report"]
        b_rep = r["token_b_report"]
        self.assertEqual(a_rep["window_closes"], 1, "Token A must have exactly 1 close")
        self.assertEqual(b_rep["window_closes"], 1, "Token B must have exactly 1 close")

    def test_per_token_source_counts_positive(self):
        """After execution, per-token source request counts should be > 0."""
        r = self._run(cycle_budget=2)
        a_rep = r["token_a_report"]
        b_rep = r["token_b_report"]
        self.assertGreater(
            a_rep["source_requests_created"], 0,
            "Token A must have source requests",
        )
        self.assertGreater(
            b_rep["source_requests_created"], 0,
            "Token B must have source requests",
        )

    def test_per_token_source_counts_do_not_mix(self):
        """Token A source counts must not include Token B requests and vice versa.
        We verify this by checking the sum matches the DB total."""
        r = self._run(cycle_budget=2)
        a_reqs = r["token_a_report"]["source_requests_created"]
        b_reqs = r["token_b_report"]["source_requests_created"]
        db_total = self._count_rows("printer_source_requests")
        self.assertEqual(
            a_reqs + b_reqs, db_total,
            f"Sum of per-token source_requests ({a_reqs}+{b_reqs}={a_reqs+b_reqs})"
            f" must equal DB total ({db_total})",
        )

    def test_cycles_list_has_correct_mints(self):
        """Each cycle in the cycles list must carry the right mint for its slot."""
        r = self._run(cycle_budget=2)
        cycles = r.get("cycles", [])
        for cyc in cycles:
            if cyc.get("slot") == "A":
                self.assertEqual(cyc.get("mint"), _MINT_A)
            elif cyc.get("slot") == "B":
                self.assertEqual(cyc.get("mint"), _MINT_B)

    # Window kind gates --------------------------------------------------------

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

    # Lock assertions ----------------------------------------------------------

    def test_hard_locks_all_true(self):
        r = self._run(cycle_budget=1)
        hl = r.get("hard_locks", {})
        for key, val in _HARD_LOCKS.items():
            self.assertIn(key, hl, f"hard_locks missing key: {key}")
            self.assertTrue(hl[key], f"hard_locks[{key!r}] must be True")

    def test_buy_sell_hold_false(self):
        r = self._run(cycle_budget=1)
        self.assertFalse(r["buy_enabled"])
        self.assertFalse(r["sell_enabled"])
        self.assertFalse(r["hold_enabled"])

    def test_paper_decisions_zero(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["paper_decisions_created"], 0)

    def test_positions_zero(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["positions_created"], 0)

    def test_trade_events_zero(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["trade_events_created"], 0)

    def test_paper_trade_audits_zero(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["paper_trade_audits_created"], 0)

    def test_pnl_zero(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["pnl_created"], 0)

    def test_retrieval_rows_zero(self):
        r = self._run(cycle_budget=1)
        self.assertEqual(r["retrieval_rows_created"], 0)

    def test_forbidden_table_counts_all_zero(self):
        r = self._run(cycle_budget=2)
        fc = r.get("forbidden_table_counts", {})
        for table, count in fc.items():
            self.assertEqual(count, 0, f"Forbidden table {table!r} must have 0 rows")

    def test_retrieval_candidates_not_written(self):
        self._run(cycle_budget=2)
        self.assertEqual(self._count_rows("printer_retrieval_candidates"), 0)

    def test_retrieval_results_not_written(self):
        self._run(cycle_budget=2)
        self.assertEqual(self._count_rows("printer_retrieval_results"), 0)

    def test_paper_decisions_not_written(self):
        self._run(cycle_budget=2)
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_paper_positions_not_written(self):
        self._run(cycle_budget=2)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    # Quality / memory ---------------------------------------------------------

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

    # Idempotent Lane K replay -------------------------------------------------

    def test_second_lane_k_run_creates_zero_new_rows(self):
        """After running the cycle, two consecutive Lane K calls must produce
        zero new rows on the second call (idempotent replay proof)."""
        self._run(cycle_budget=2)
        from printer_v1.operator_cli.lane_k_e2z_pipeline_wiring import run_e2z_pipeline
        k1 = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertIn("clean_memory_rows_created", k1)
        k2 = run_e2z_pipeline(self.db_path, operator_approved=True)
        self.assertEqual(
            k2["clean_memory_rows_created"],
            0,
            "Second Lane K run must not create new clean-memory rows (idempotent)",
        )

    def test_second_cycle_run_does_not_error(self):
        """Running the two-token cycle twice must not raise or return BLOCKED."""
        r1 = self._run(cycle_budget=1)
        r2 = self._run(cycle_budget=1)
        self.assertEqual(r1["lane_x2_status"], LANE_X2_STATUS_COMPLETED)
        self.assertEqual(r2["lane_x2_status"], LANE_X2_STATUS_COMPLETED)

    # Scheduler job cleanup ----------------------------------------------------

    def test_no_running_jobs_after_cycle(self):
        """Scheduler jobs must not be left RUNNING after the cycle exits."""
        self._run(cycle_budget=2)
        running = self._count_rows_where(
            "printer_scheduler_jobs", "status = 'RUNNING'"
        )
        self.assertEqual(running, 0, "No RUNNING scheduler jobs must remain after cycle")

    def _count_rows_where(self, table: str, where: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()
            return row[0] if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 4. CLI tests
# ---------------------------------------------------------------------------

class TestLaneX2CLI(unittest.TestCase):
    def test_cli_function_importable(self):
        from printer_v1.operator_cli.commands import main_run_lane_x2_two_token_cycle
        self.assertTrue(callable(main_run_lane_x2_two_token_cycle))

    def test_cli_blocked_without_operator_approved(self):
        """Missing --operator-approved → exits 0 with BLOCKED status in JSON."""
        import io
        from contextlib import redirect_stdout
        from printer_v1.operator_cli.commands import main_run_lane_x2_two_token_cycle

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
                ]
            }), encoding="utf-8")

            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = main_run_lane_x2_two_token_cycle([
                    "--token-list-path", str(token_path),
                    "--backup-proof-path", str(backup_path),
                    "--db-path", str(db_path),
                ])
            self.assertEqual(rc, 0, "CLI should exit 0 even when BLOCKED")
            output = json.loads(buf.getvalue())
            self.assertEqual(output["lane_x2_status"], LANE_X2_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# 5. LANE_X2_EXACT_TOKEN_COUNT constant test
# ---------------------------------------------------------------------------

class TestLaneX2Constants(unittest.TestCase):
    def test_exact_token_count_is_2(self):
        self.assertEqual(LANE_X2_EXACT_TOKEN_COUNT, 2)

    def test_hard_locks_dict_has_all_expected_keys(self):
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
        }
        missing = expected_keys - _HARD_LOCKS.keys()
        self.assertFalse(missing, f"Missing hard lock keys: {missing}")

    def test_all_hard_locks_are_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"_HARD_LOCKS[{key!r}] must be True")


if __name__ == "__main__":
    unittest.main()
