"""Lane X3 — Post-Cycle Cooldown / Archive / Rotation Lifecycle Wiring tests.

Validates:
- Completed memory cycle can enter cooldown (lifecycle event + tracking queue row).
- Archive-after-memory-window creates an ARCHIVED tracking queue row.
- Stale token/pair is not immediately re-selected (cooldown gate blocks).
- Intentional revival/reopen is possible (new QUEUED entry overrides cooldown).
- Lifecycle events are recorded in printer_token_lifecycle_events.
- Dirty/audit-only memory is preserved after cooldown or archive transitions.
- X2 two-token proof behavior is unchanged (regression).
- All retrieval/paper/BUY/position/PnL locks remain unchanged.
- Hard locks dict has all 23 keys set to True.
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
from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
    LANE_X3_STATUS_ARCHIVED,
    LANE_X3_STATUS_BLOCKED,
    LANE_X3_STATUS_COOLDOWN_ENTERED,
    LANE_X3_STATUS_NO_ACTION,
    LANE_X3_STATUS_REOPENED,
    _HARD_LOCKS,
    archive_after_memory_window,
    check_forbidden_tables,
    check_memory_preservation,
    check_x3_cooldown_gate,
    enter_cooldown_after_window,
    evaluate_post_cycle_lifecycle,
    get_token_lifecycle_status,
    is_token_in_cooldown_or_archived,
    reopen_token,
)
from printer_v1.operator_cli.lane_x2_two_token_runner import (
    LANE_X2_STATUS_BLOCKED,
    LANE_X2_STATUS_COMPLETED,
    LANE_X2_STATUS_STOPPED,
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

_MINT_X3 = "7aX3testMintXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
_PAIR_X3 = "LaneX3TestPairXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"


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
                    "symbol": "X3T",
                    "name": "Lane X3 Test Token",
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


def _make_x2_result(
    *,
    status: str = LANE_X2_STATUS_COMPLETED,
    mint_a: str = _MINT_A,
    mint_b: str = _MINT_B,
    window_closes_a: int = 1,
    window_closes_b: int = 0,
) -> dict[str, Any]:
    """Build a minimal synthetic X2 result for evaluator tests."""
    return {
        "lane_x2_status": status,
        "token_a_report": {
            "slot": "A",
            "mint": mint_a,
            "window_closes": window_closes_a,
            "snapshots_created": window_closes_a * 1,
        },
        "token_b_report": {
            "slot": "B",
            "mint": mint_b,
            "window_closes": window_closes_b,
            "snapshots_created": window_closes_b * 1,
        },
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
            return int(row[0]) if row else 0
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _write_x2_token_file(self) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens_x2.json"
        tf.write_text(
            json.dumps({
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
            }),
            encoding="utf-8",
        )
        return tf

    def _run_x2(self, *, cycle_budget: int = 1) -> dict[str, Any]:
        return run_two_token_memory_factory_cycle(
            self._write_x2_token_file(),
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            duration_profile="1h",
            window_kind="WINDOW_15M",
            _adapter_map=_make_adapter_map(),
            _cycle_budget=cycle_budget,
        )

    def _cooldown_a(self) -> dict[str, Any]:
        return enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)

    def _cooldown_b(self) -> dict[str, Any]:
        return enter_cooldown_after_window(self.db_path, _MINT_B, _PAIR_B)

    def _archive_a(self) -> dict[str, Any]:
        return archive_after_memory_window(self.db_path, _MINT_A, _PAIR_A)

    def _reopen_a(self) -> dict[str, Any]:
        return reopen_token(self.db_path, _MINT_A, _PAIR_A)


# ---------------------------------------------------------------------------
# 1. Cooldown entry — ENTER_COOLDOWN lifecycle event + COOLDOWN queue row
# ---------------------------------------------------------------------------

class TestX3CooldownEntry(_DbBase):
    """Tests for enter_cooldown_after_window."""

    def test_status_is_cooldown_entered(self):
        result = self._cooldown_a()
        self.assertEqual(result["lane_x3_status"], LANE_X3_STATUS_COOLDOWN_ENTERED)

    def test_cooldown_creates_tracking_queue_row(self):
        before = self._count_rows("printer_tracking_queue")
        self._cooldown_a()
        after = self._count_rows("printer_tracking_queue")
        self.assertGreater(after, before)

    def test_cooldown_queue_status_is_cooldown(self):
        self._cooldown_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT queue_status FROM printer_tracking_queue ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["queue_status"], "COOLDOWN")
        finally:
            conn.close()

    def test_cooldown_creates_lifecycle_event(self):
        before = self._count_rows("printer_token_lifecycle_events")
        self._cooldown_a()
        after = self._count_rows("printer_token_lifecycle_events")
        self.assertGreater(after, before)

    def test_cooldown_event_is_enter_cooldown(self):
        self._cooldown_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT lifecycle_event FROM printer_token_lifecycle_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(row["lifecycle_event"], "ENTER_COOLDOWN")
        finally:
            conn.close()

    def test_cooldown_previous_state_is_track_fast(self):
        self._cooldown_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT previous_state FROM printer_token_lifecycle_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["previous_state"], "TRACK_FAST")
        finally:
            conn.close()

    def test_cooldown_new_state_is_cooldown(self):
        self._cooldown_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT new_state FROM printer_token_lifecycle_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["new_state"], "COOLDOWN")
        finally:
            conn.close()

    def test_cooldown_result_has_token_id_and_pair_id(self):
        result = self._cooldown_a()
        self.assertIn("token_id", result)
        self.assertIn("pair_id", result)
        self.assertIsInstance(result["token_id"], int)
        self.assertIsInstance(result["pair_id"], int)

    def test_cooldown_result_has_event_id(self):
        result = self._cooldown_a()
        self.assertIn("lifecycle_event_id", result)
        self.assertIsInstance(result["lifecycle_event_id"], int)

    def test_cooldown_result_has_queue_id(self):
        result = self._cooldown_a()
        self.assertIn("queue_id", result)
        self.assertIsInstance(result["queue_id"], int)

    def test_cooldown_memory_tables_preserved(self):
        result = self._cooldown_a()
        self.assertTrue(result.get("memory_tables_preserved"))

    def test_cooldown_creates_token_record_if_absent(self):
        """Token record is auto-created when not in DB."""
        before = self._count_rows("printer_tokens")
        self._cooldown_a()
        after = self._count_rows("printer_tokens")
        self.assertGreater(after, before)

    def test_cooldown_creates_pair_record_if_absent(self):
        before = self._count_rows("printer_pairs")
        self._cooldown_a()
        after = self._count_rows("printer_pairs")
        self.assertGreater(after, before)

    def test_cooldown_idempotent_token_record(self):
        """Calling twice does not duplicate the token record."""
        self._cooldown_a()
        tokens_after_first = self._count_rows("printer_tokens")
        self._cooldown_a()
        tokens_after_second = self._count_rows("printer_tokens")
        self.assertEqual(tokens_after_first, tokens_after_second)

    def test_cooldown_event_payload_stored(self):
        enter_cooldown_after_window(
            self.db_path, _MINT_A, _PAIR_A,
            event_payload={"memory_window_id": 42, "reason": "test"},
        )
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT event_payload_json FROM printer_token_lifecycle_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            payload = json.loads(row["event_payload_json"])
            self.assertEqual(payload.get("memory_window_id"), 42)
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# 2. Archive entry — ARCHIVE_AFTER_MEMORY_WINDOW lifecycle event
# ---------------------------------------------------------------------------

class TestX3ArchiveEntry(_DbBase):
    """Tests for archive_after_memory_window."""

    def test_status_is_archived(self):
        result = self._archive_a()
        self.assertEqual(result["lane_x3_status"], LANE_X3_STATUS_ARCHIVED)

    def test_archive_creates_tracking_queue_row(self):
        before = self._count_rows("printer_tracking_queue")
        self._archive_a()
        after = self._count_rows("printer_tracking_queue")
        self.assertGreater(after, before)

    def test_archive_queue_status_is_archived(self):
        self._archive_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT queue_status FROM printer_tracking_queue ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["queue_status"], "ARCHIVED")
        finally:
            conn.close()

    def test_archive_creates_lifecycle_event(self):
        before = self._count_rows("printer_token_lifecycle_events")
        self._archive_a()
        after = self._count_rows("printer_token_lifecycle_events")
        self.assertGreater(after, before)

    def test_archive_event_is_archive_after_memory_window(self):
        self._archive_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT lifecycle_event FROM printer_token_lifecycle_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["lifecycle_event"], "ARCHIVE_AFTER_MEMORY_WINDOW")
        finally:
            conn.close()

    def test_archive_new_state_is_archived(self):
        self._archive_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT new_state FROM printer_token_lifecycle_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["new_state"], "ARCHIVED")
        finally:
            conn.close()

    def test_archive_memory_tables_preserved(self):
        result = self._archive_a()
        self.assertTrue(result.get("memory_tables_preserved"))


# ---------------------------------------------------------------------------
# 3. Cooldown gate — stale re-selection prevention
# ---------------------------------------------------------------------------

class TestX3CooldownGate(_DbBase):
    """Tests for is_token_in_cooldown_or_archived and check_x3_cooldown_gate."""

    def test_fresh_mint_not_in_cooldown(self):
        self.assertFalse(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))

    def test_fresh_mint_gate_passes(self):
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A, _MINT_B])
        self.assertEqual(blocked, [])

    def test_cooldown_mint_is_in_cooldown(self):
        self._cooldown_a()
        self.assertTrue(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))

    def test_cooldown_gate_blocks_stale_mint(self):
        """After entering cooldown, the cooldown gate returns a non-empty block list."""
        self._cooldown_a()
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A])
        self.assertGreater(len(blocked), 0)

    def test_cooldown_gate_message_contains_mint(self):
        self._cooldown_a()
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A])
        self.assertTrue(any(_MINT_A in msg for msg in blocked))

    def test_cooldown_only_blocks_affected_mint(self):
        """Cooldown for MINT_A does not block MINT_B."""
        self._cooldown_a()
        self.assertFalse(is_token_in_cooldown_or_archived(self.db_path, _MINT_B))

    def test_gate_blocks_when_one_of_two_mints_in_cooldown(self):
        """Even if only one mint is in cooldown, the gate should report that one."""
        self._cooldown_a()
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A, _MINT_B])
        self.assertEqual(len(blocked), 1)

    def test_archive_mint_is_in_cooldown_or_archived(self):
        self._archive_a()
        self.assertTrue(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))

    def test_archive_gate_blocks_stale_mint(self):
        self._archive_a()
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A])
        self.assertGreater(len(blocked), 0)

    def test_get_token_lifecycle_status_fresh(self):
        status = get_token_lifecycle_status(self.db_path, _MINT_A)
        self.assertFalse(status["in_cooldown_or_archived"])
        self.assertIsNone(status["most_recent_queue_status"])

    def test_get_token_lifecycle_status_in_cooldown(self):
        self._cooldown_a()
        status = get_token_lifecycle_status(self.db_path, _MINT_A)
        self.assertTrue(status["in_cooldown_or_archived"])
        self.assertEqual(status["most_recent_queue_status"], "COOLDOWN")


# ---------------------------------------------------------------------------
# 4. Revival / reopen — intentional re-selection allowed
# ---------------------------------------------------------------------------

class TestX3Reopen(_DbBase):
    """Tests for reopen_token."""

    def test_status_is_reopened(self):
        self._cooldown_a()
        result = self._reopen_a()
        self.assertEqual(result["lane_x3_status"], LANE_X3_STATUS_REOPENED)

    def test_reopen_creates_queued_entry(self):
        self._cooldown_a()
        self._reopen_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT queue_status FROM printer_tracking_queue ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["queue_status"], "QUEUED")
        finally:
            conn.close()

    def test_reopen_creates_lifecycle_event(self):
        self._cooldown_a()
        before = self._count_rows("printer_token_lifecycle_events")
        self._reopen_a()
        after = self._count_rows("printer_token_lifecycle_events")
        self.assertGreater(after, before)

    def test_reopen_event_is_reopen_revived_token(self):
        self._cooldown_a()
        self._reopen_a()
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            row = conn.execute(
                "SELECT lifecycle_event FROM printer_token_lifecycle_events ORDER BY id DESC LIMIT 1"
            ).fetchone()
            self.assertEqual(row["lifecycle_event"], "REOPEN_REVIVED_TOKEN")
        finally:
            conn.close()

    def test_reopen_clears_cooldown_for_gate(self):
        """After reopen, cooldown gate no longer blocks the mint."""
        self._cooldown_a()
        self.assertTrue(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))
        self._reopen_a()
        self.assertFalse(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))

    def test_gate_passes_after_reopen(self):
        self._cooldown_a()
        self._reopen_a()
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A])
        self.assertEqual(blocked, [])

    def test_reopen_without_prior_cooldown_still_works(self):
        """Reopen can be called even without a prior cooldown entry."""
        result = self._reopen_a()
        self.assertEqual(result["lane_x3_status"], LANE_X3_STATUS_REOPENED)

    def test_reopen_after_archive_clears_gate(self):
        self._archive_a()
        self.assertTrue(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))
        self._reopen_a()
        self.assertFalse(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))

    def test_reopen_result_has_event_id(self):
        self._cooldown_a()
        result = self._reopen_a()
        self.assertIn("lifecycle_event_id", result)
        self.assertIsInstance(result["lifecycle_event_id"], int)


# ---------------------------------------------------------------------------
# 5. Memory preservation — dirty/audit-only memory not deleted
# ---------------------------------------------------------------------------

class TestX3MemoryPreservation(_DbBase):
    """Proves that lifecycle transitions do not delete snapshots or memory windows."""

    def _run_x2_and_count(self) -> dict[str, int]:
        self._run_x2(cycle_budget=1)
        return {
            "snapshots": self._count_rows("printer_token_snapshots"),
            "memory_windows": self._count_rows("printer_memory_windows"),
            "source_requests": self._count_rows("printer_source_requests"),
        }

    def test_cooldown_does_not_delete_snapshots(self):
        counts = self._run_x2_and_count()
        snap_before = counts["snapshots"]
        self._cooldown_a()
        snap_after = self._count_rows("printer_token_snapshots")
        self.assertEqual(snap_before, snap_after, "Snapshots must not be deleted on cooldown")

    def test_cooldown_does_not_delete_memory_windows(self):
        counts = self._run_x2_and_count()
        mw_before = counts["memory_windows"]
        self._cooldown_a()
        mw_after = self._count_rows("printer_memory_windows")
        self.assertEqual(mw_before, mw_after, "Memory windows must not be deleted on cooldown")

    def test_archive_does_not_delete_snapshots(self):
        counts = self._run_x2_and_count()
        snap_before = counts["snapshots"]
        self._archive_a()
        snap_after = self._count_rows("printer_token_snapshots")
        self.assertEqual(snap_before, snap_after, "Snapshots must not be deleted on archive")

    def test_archive_does_not_delete_memory_windows(self):
        counts = self._run_x2_and_count()
        mw_before = counts["memory_windows"]
        self._archive_a()
        mw_after = self._count_rows("printer_memory_windows")
        self.assertEqual(mw_before, mw_after, "Memory windows must not be deleted on archive")

    def test_check_memory_preservation_returns_counts(self):
        self._run_x2(cycle_budget=1)
        preservation = check_memory_preservation(self.db_path)
        self.assertIsInstance(preservation, dict)
        self.assertIn("printer_memory_windows", preservation)
        self.assertIn("printer_token_snapshots", preservation)

    def test_cooldown_and_reopen_both_preserve_memory(self):
        self._run_x2_and_count()
        snap_before = self._count_rows("printer_token_snapshots")
        mw_before = self._count_rows("printer_memory_windows")
        self._cooldown_a()
        self._reopen_a()
        self.assertEqual(self._count_rows("printer_token_snapshots"), snap_before)
        self.assertEqual(self._count_rows("printer_memory_windows"), mw_before)

    def test_dirty_memory_preserved_after_cooldown(self):
        """Dirty memory audit rows are not deleted by lifecycle transitions."""
        self._run_x2(cycle_budget=1)
        audit_before = self._count_rows("printer_memory_audit_reports")
        self._cooldown_a()
        audit_after = self._count_rows("printer_memory_audit_reports")
        self.assertEqual(audit_before, audit_after)

    def test_zero_clean_memories_valid_after_cooldown(self):
        """Entering cooldown on a DB with zero clean memories is still valid."""
        result = self._cooldown_a()
        self.assertEqual(result["lane_x3_status"], LANE_X3_STATUS_COOLDOWN_ENTERED)

    def test_new_evidence_possible_after_cooldown(self):
        """After cooldown, a second X2 run can still create new evidence (if reopened)."""
        self._run_x2(cycle_budget=1)
        snap_after_first = self._count_rows("printer_token_snapshots")
        self._cooldown_a()
        self._cooldown_b()
        self._reopen_a()
        self._reopen_a()  # No error on double reopen
        result2 = self._run_x2(cycle_budget=1)
        snap_after_second = self._count_rows("printer_token_snapshots")
        # X2 ran again and created more evidence
        self.assertGreaterEqual(snap_after_second, snap_after_first)
        self.assertIn(result2["lane_x2_status"], {LANE_X2_STATUS_COMPLETED, LANE_X2_STATUS_STOPPED})


# ---------------------------------------------------------------------------
# 6. Post-cycle evaluator — evaluate_post_cycle_lifecycle
# ---------------------------------------------------------------------------

class TestX3PostCycleEvaluator(_DbBase):
    """Tests for evaluate_post_cycle_lifecycle."""

    def test_evaluator_enters_cooldown_for_completed_token(self):
        x2_result = _make_x2_result(window_closes_a=1, window_closes_b=0)
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertIn(result["lane_x3_status"], {LANE_X3_STATUS_COOLDOWN_ENTERED, LANE_X3_STATUS_NO_ACTION})
        cooldown_count = result["cooldown_entered_count"]
        self.assertGreaterEqual(cooldown_count, 1, "Token A (1 window close) should enter cooldown")

    def test_evaluator_skips_uncycled_token(self):
        """Token B with zero window closes gets NO_ACTION."""
        x2_result = _make_x2_result(window_closes_a=1, window_closes_b=0)
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        no_action = [
            t for t in result["transitions"]
            if t.get("lane_x3_status") == LANE_X3_STATUS_NO_ACTION
        ]
        self.assertGreater(len(no_action), 0, "MINT_B with 0 closes should be NO_ACTION")

    def test_evaluator_archive_policy(self):
        x2_result = _make_x2_result(window_closes_a=1, window_closes_b=1)
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
            archive_policy="archive",
        )
        self.assertGreaterEqual(result["archived_count"], 1)
        archived = [
            t for t in result["transitions"]
            if t.get("lane_x3_status") == LANE_X3_STATUS_ARCHIVED
        ]
        self.assertGreater(len(archived), 0)

    def test_evaluator_both_tokens_with_window_closes(self):
        x2_result = _make_x2_result(window_closes_a=1, window_closes_b=1)
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertEqual(result["cooldown_entered_count"], 2)
        self.assertEqual(result["no_action_count"], 0)

    def test_evaluator_blocks_on_non_terminal_status(self):
        x2_result = _make_x2_result(status="LANE_X2_BLOCKED")
        result = evaluate_post_cycle_lifecycle(self.db_path, x2_result)
        self.assertEqual(result["lane_x3_status"], LANE_X3_STATUS_BLOCKED)
        self.assertIn("blocked_reason", result)

    def test_evaluator_accepts_stopped_status(self):
        x2_result = _make_x2_result(status=LANE_X2_STATUS_STOPPED, window_closes_a=1)
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A},
        )
        self.assertNotEqual(result["lane_x3_status"], LANE_X3_STATUS_BLOCKED)

    def test_evaluator_returns_transitions_list(self):
        x2_result = _make_x2_result()
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertIn("transitions", result)
        self.assertIsInstance(result["transitions"], list)

    def test_evaluator_returns_memory_preserved_flag(self):
        x2_result = _make_x2_result()
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertTrue(result.get("memory_tables_preserved"))

    def test_evaluator_returns_hard_locks(self):
        x2_result = _make_x2_result()
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertIn("hard_locks", result)
        self.assertTrue(all(result["hard_locks"].values()))

    def test_evaluator_buy_sell_hold_false(self):
        x2_result = _make_x2_result()
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertFalse(result.get("buy_enabled"))
        self.assertFalse(result.get("sell_enabled"))
        self.assertFalse(result.get("hold_enabled"))

    def test_evaluator_no_paper_or_pnl_rows(self):
        x2_result = _make_x2_result()
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertEqual(result.get("paper_decisions_created"), 0)
        self.assertEqual(result.get("positions_created"), 0)
        self.assertEqual(result.get("pnl_created"), 0)
        self.assertEqual(result.get("retrieval_rows_created"), 0)

    def test_evaluator_zero_clean_memories_valid(self):
        x2_result = _make_x2_result()
        result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertTrue(result.get("zero_clean_memories_is_valid"))

    def test_evaluator_with_live_x2_result(self):
        """Integration: run an actual X2 cycle and evaluate post-cycle lifecycle."""
        x2_result = self._run_x2(cycle_budget=1)
        self.assertIn(
            x2_result["lane_x2_status"],
            {LANE_X2_STATUS_COMPLETED, LANE_X2_STATUS_STOPPED},
        )
        eval_result = evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        self.assertIn(
            eval_result["lane_x3_status"],
            {LANE_X3_STATUS_COOLDOWN_ENTERED, LANE_X3_STATUS_NO_ACTION},
        )
        self.assertIsInstance(eval_result["transitions"], list)

    def test_evaluator_creates_events_in_db_after_live_x2(self):
        """After evaluating a real X2 result, lifecycle events exist in DB."""
        self._run_x2(cycle_budget=1)
        before = self._count_rows("printer_token_lifecycle_events")
        x2_result = _make_x2_result(window_closes_a=1, window_closes_b=0)
        evaluate_post_cycle_lifecycle(
            self.db_path, x2_result,
            pair_address_by_mint={_MINT_A: _PAIR_A, _MINT_B: _PAIR_B},
        )
        after = self._count_rows("printer_token_lifecycle_events")
        self.assertGreater(after, before)


# ---------------------------------------------------------------------------
# 7. Stale re-selection prevention (end-to-end gate flow)
# ---------------------------------------------------------------------------

class TestX3StaleReselection(_DbBase):
    """End-to-end proof that stale tokens are blocked and revival works."""

    def test_stale_token_not_immediately_reselected(self):
        """After cooldown, check_x3_cooldown_gate blocks the stale token."""
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        enter_cooldown_after_window(self.db_path, _MINT_B, _PAIR_B)

        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A, _MINT_B])
        self.assertEqual(len(blocked), 2, "Both stale tokens should be blocked")

    def test_only_stale_token_is_blocked(self):
        """Fresh mint is not blocked even when another is in cooldown."""
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A, _MINT_B])
        self.assertEqual(len(blocked), 1)
        self.assertFalse(is_token_in_cooldown_or_archived(self.db_path, _MINT_B))

    def test_revival_allows_reselection_for_one_mint(self):
        """After reopen for MINT_A, MINT_A is no longer blocked."""
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        enter_cooldown_after_window(self.db_path, _MINT_B, _PAIR_B)
        reopen_token(self.db_path, _MINT_A, _PAIR_A)

        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A, _MINT_B])
        blocked_mints = [msg for msg in blocked if _MINT_A in msg]
        self.assertEqual(len(blocked_mints), 0, "MINT_A should be unblocked after revival")

    def test_full_revival_allows_full_reselection(self):
        """After reopening both mints, gate passes for both."""
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        enter_cooldown_after_window(self.db_path, _MINT_B, _PAIR_B)
        reopen_token(self.db_path, _MINT_A, _PAIR_A)
        reopen_token(self.db_path, _MINT_B, _PAIR_B)

        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A, _MINT_B])
        self.assertEqual(len(blocked), 0)

    def test_archive_then_revival(self):
        """Archive followed by reopen restores passage."""
        archive_after_memory_window(self.db_path, _MINT_A, _PAIR_A)
        self.assertTrue(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))
        reopen_token(self.db_path, _MINT_A, _PAIR_A)
        self.assertFalse(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))

    def test_multiple_cooldowns_then_reopen(self):
        """Multiple cooldown entries — reopen overrides via most-recent logic."""
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        reopen_token(self.db_path, _MINT_A, _PAIR_A)
        self.assertFalse(is_token_in_cooldown_or_archived(self.db_path, _MINT_A))


# ---------------------------------------------------------------------------
# 8. X2 regression — two-token proof behavior unchanged
# ---------------------------------------------------------------------------

class TestX3X2Regression(_DbBase):
    """Proves existing X2 two-token proof behavior is unaffected by Lane X3."""

    def test_x2_still_completes_with_budget_1(self):
        result = self._run_x2(cycle_budget=1)
        self.assertIn(
            result["lane_x2_status"],
            {LANE_X2_STATUS_COMPLETED, LANE_X2_STATUS_STOPPED},
        )

    def test_x2_selected_token_count_is_2(self):
        result = self._run_x2(cycle_budget=1)
        self.assertEqual(result.get("selected_token_count"), 2)

    def test_x2_token_a_mint_in_result(self):
        result = self._run_x2(cycle_budget=1)
        self.assertEqual(result.get("token_a_mint"), _MINT_A)

    def test_x2_token_b_mint_in_result(self):
        result = self._run_x2(cycle_budget=1)
        self.assertEqual(result.get("token_b_mint"), _MINT_B)

    def test_x2_hard_locks_all_true(self):
        result = self._run_x2(cycle_budget=1)
        for key, val in result.get("hard_locks", {}).items():
            self.assertTrue(val, f"hard lock {key!r} must be True in X2 result")

    def test_x2_buy_sell_hold_false(self):
        result = self._run_x2(cycle_budget=1)
        self.assertFalse(result.get("buy_enabled"))
        self.assertFalse(result.get("sell_enabled"))
        self.assertFalse(result.get("hold_enabled"))

    def test_x2_paper_rows_zero(self):
        result = self._run_x2(cycle_budget=1)
        self.assertEqual(result.get("paper_decisions_created"), 0)
        self.assertEqual(result.get("positions_created"), 0)

    def test_x2_forbidden_tables_zero(self):
        self._run_x2(cycle_budget=1)
        for table in (
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
        ):
            self.assertEqual(
                self._count_rows(table), 0,
                f"Forbidden table {table!r} must remain zero after X2+X3",
            )

    def test_x3_has_no_impact_on_x2_forbidden_tables(self):
        """Running X3 lifecycle functions also does not touch forbidden tables."""
        self._run_x2(cycle_budget=1)
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        archive_after_memory_window(self.db_path, _MINT_B, _PAIR_B)
        reopen_token(self.db_path, _MINT_A, _PAIR_A)
        for table in (
            "printer_paper_decisions",
            "printer_paper_positions",
        ):
            self.assertEqual(self._count_rows(table), 0)

    def test_x2_gate_check_passes_on_fresh_db(self):
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A, _MINT_B])
        self.assertEqual(blocked, [])

    def test_x2_cycle_then_x3_cooldown_then_gate_blocks(self):
        self._run_x2(cycle_budget=1)
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        blocked = check_x3_cooldown_gate(self.db_path, [_MINT_A])
        self.assertGreater(len(blocked), 0)

    def test_x2_runs_again_cleanly_after_reopen(self):
        """After cooldown + reopen, X2 can run a second cycle without errors."""
        self._run_x2(cycle_budget=1)
        enter_cooldown_after_window(self.db_path, _MINT_A, _PAIR_A)
        enter_cooldown_after_window(self.db_path, _MINT_B, _PAIR_B)
        reopen_token(self.db_path, _MINT_A, _PAIR_A)
        reopen_token(self.db_path, _MINT_B, _PAIR_B)

        result2 = self._run_x2(cycle_budget=1)
        self.assertIn(
            result2["lane_x2_status"],
            {LANE_X2_STATUS_COMPLETED, LANE_X2_STATUS_STOPPED},
        )


# ---------------------------------------------------------------------------
# 9. Hard locks and forbidden tables
# ---------------------------------------------------------------------------

class TestX3Locks(_DbBase):
    """Verifies all hard locks are present and all forbidden tables remain zero."""

    def test_hard_locks_has_expected_keys(self):
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
            "no_memory_deletion",
        }
        self.assertEqual(set(_HARD_LOCKS.keys()), expected_keys)

    def test_all_hard_locks_are_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_forbidden_tables_zero_on_fresh_db(self):
        counts = check_forbidden_tables(self.db_path)
        for table, count in counts.items():
            self.assertEqual(count, 0, f"Forbidden table {table!r} should be 0")

    def test_forbidden_tables_zero_after_cooldown(self):
        self._cooldown_a()
        counts = check_forbidden_tables(self.db_path)
        for table, count in counts.items():
            self.assertEqual(count, 0, f"Forbidden table {table!r} must remain 0 after cooldown")

    def test_forbidden_tables_zero_after_archive(self):
        self._archive_a()
        counts = check_forbidden_tables(self.db_path)
        for table, count in counts.items():
            self.assertEqual(count, 0)

    def test_forbidden_tables_zero_after_reopen(self):
        self._cooldown_a()
        self._reopen_a()
        counts = check_forbidden_tables(self.db_path)
        for table, count in counts.items():
            self.assertEqual(count, 0)

    def test_retrieval_tables_not_written(self):
        self._cooldown_a()
        self._archive_a()
        self._reopen_a()
        self.assertEqual(self._count_rows("printer_memory_retrieval_queries"), 0)
        self.assertEqual(self._count_rows("printer_memory_retrieval_matches"), 0)

    def test_paper_decision_tables_not_written(self):
        self._cooldown_a()
        self._archive_a()
        self._reopen_a()
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)


# ---------------------------------------------------------------------------
# 10. Import and constant tests
# ---------------------------------------------------------------------------

class TestX3Constants(unittest.TestCase):
    """Basic import and constant sanity checks."""

    def test_module_importable(self):
        from printer_v1.operator_cli import lane_x3_post_cycle_lifecycle
        self.assertIsNotNone(lane_x3_post_cycle_lifecycle)

    def test_status_constants_are_strings(self):
        for const in (
            LANE_X3_STATUS_COOLDOWN_ENTERED,
            LANE_X3_STATUS_ARCHIVED,
            LANE_X3_STATUS_REOPENED,
            LANE_X3_STATUS_NO_ACTION,
            LANE_X3_STATUS_BLOCKED,
        ):
            self.assertIsInstance(const, str)

    def test_hard_locks_count(self):
        self.assertEqual(len(_HARD_LOCKS), 23)

    def test_all_hard_locks_true(self):
        self.assertTrue(all(_HARD_LOCKS.values()))

    def test_no_memory_deletion_lock_present(self):
        self.assertIn("no_memory_deletion", _HARD_LOCKS)
        self.assertTrue(_HARD_LOCKS["no_memory_deletion"])

    def test_functions_importable(self):
        from printer_v1.operator_cli.lane_x3_post_cycle_lifecycle import (
            archive_after_memory_window,
            check_forbidden_tables,
            check_memory_preservation,
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
            evaluate_post_cycle_lifecycle,
            get_token_lifecycle_status,
            is_token_in_cooldown_or_archived,
            reopen_token,
        )
        for fn in (
            archive_after_memory_window,
            check_forbidden_tables,
            check_memory_preservation,
            check_x3_cooldown_gate,
            enter_cooldown_after_window,
            evaluate_post_cycle_lifecycle,
            get_token_lifecycle_status,
            is_token_in_cooldown_or_archived,
            reopen_token,
        ):
            self.assertTrue(callable(fn))


if __name__ == "__main__":
    unittest.main()
