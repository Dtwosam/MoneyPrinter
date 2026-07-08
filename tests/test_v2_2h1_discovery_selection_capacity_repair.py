"""V2-2H.1 — Discovery/Selection Candidate Cap, Reporting, and Schema Readiness.

Targeted unit tests for the first safe repair slice of V2-2H:
  A. Configurable bounded candidate cap (repairs the hardcoded 1-3 cap).
  C. Candidate-stage reporting separation.
  D. Selection-batch schema readiness check (fail-fast, read-only).

Locks preserved: no discovery runs, no source fetching, no live DB mutation,
no memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD, no
positions/trades/audits/PnL, no scoring/ranking/confidence/weighted logic.
"""

from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.discovery.selection_batch import (
    SelectionBatchSchemaNotReadyError,
    check_selection_batch_schema_ready,
    persist_selection_batch,
)
from printer_v1.operator_cli.commands import (
    _DISCOVER_CANDIDATES_CAP_DEFAULT,
    _DISCOVER_CANDIDATES_CAP_MAX,
    _DISCOVER_CANDIDATES_CAP_MIN,
    _validate_discover_candidates_args,
    build_discover_candidates_once_payload,
)


def _args(**overrides: object) -> argparse.Namespace:
    values = {
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 5,
        "source_name": "dexscreener",
        "timeout_seconds": 5.0,
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _fresh_db_with_migrations() -> pathlib.Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        db_path = pathlib.Path(f.name)
    apply_migrations(db_path)
    return db_path


def _fresh_db_without_migrations() -> pathlib.Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        db_path = pathlib.Path(f.name)
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE placeholder_only (id INTEGER PRIMARY KEY)")
    conn.commit()
    conn.close()
    return db_path


def _success_transport(context):
    del context
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": "h1-fresh-pair-1",
                "baseToken": {"address": "h1-fresh-mint-1", "symbol": "H1A", "name": "H1 One"},
                "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                "dexId": "raydium",
                "priceUsd": "0.001",
                "liquidity": {"usd": 8000},
                "volume": {"m5": 2500, "h1": 12000, "h24": 50000},
                "txns": {"m5": {"buys": 8, "sells": 6}, "h1": {"buys": 40, "sells": 25}},
            },
            {
                "chainId": "solana",
                "pairAddress": "h1-fresh-pair-2",
                "baseToken": {"address": "h1-fresh-mint-2", "symbol": "H1B", "name": "H1 Two"},
                "quoteToken": {"address": "So11111111111111111111111111111111111111112"},
                "dexId": "raydium",
                "priceUsd": "0.002",
                "liquidity": {"usd": 3000},
                "volume": {"m5": 50, "h1": 300, "h24": 1000},
                "txns": {"m5": {"buys": 1, "sells": 1}},
            },
        ]
    }


# ---------------------------------------------------------------------------
# A. Candidate cap repair
# ---------------------------------------------------------------------------

class TestCandidateCapRepair(unittest.TestCase):

    def test_bounds_are_wider_than_old_hardcoded_cap(self):
        self.assertEqual(_DISCOVER_CANDIDATES_CAP_MIN, 1)
        self.assertEqual(_DISCOVER_CANDIDATES_CAP_MAX, 50)
        self.assertGreater(_DISCOVER_CANDIDATES_CAP_MAX, 3)

    def test_default_cap_is_bounded_and_above_old_default(self):
        self.assertGreaterEqual(_DISCOVER_CANDIDATES_CAP_DEFAULT, _DISCOVER_CANDIDATES_CAP_MIN)
        self.assertLessEqual(_DISCOVER_CANDIDATES_CAP_DEFAULT, _DISCOVER_CANDIDATES_CAP_MAX)
        self.assertEqual(_DISCOVER_CANDIDATES_CAP_DEFAULT, 10)

    def test_accepts_value_above_old_hardcoded_cap_of_three(self):
        for value in (4, 10, 25, 50):
            with self.subTest(value=value):
                # Must not raise.
                _validate_discover_candidates_args(_args(max_candidates=value))

    def test_accepts_lower_bound(self):
        _validate_discover_candidates_args(_args(max_candidates=1))

    def test_rejects_value_above_upper_bound(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            _validate_discover_candidates_args(_args(max_candidates=51))

    def test_rejects_zero(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            _validate_discover_candidates_args(_args(max_candidates=0))

    def test_rejects_negative(self):
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            _validate_discover_candidates_args(_args(max_candidates=-5))

    def test_discovery_remains_bounded_not_unbounded(self):
        # A very large value must still be rejected -- the cap repair widens
        # the safe range, it does not remove the cap.
        with self.assertRaisesRegex(ValueError, "between 1 and 50"):
            _validate_discover_candidates_args(_args(max_candidates=10_000))

    def test_other_validations_still_enforced(self):
        with self.assertRaisesRegex(ValueError, "operator approval"):
            _validate_discover_candidates_args(_args(operator_approved=False))
        with self.assertRaisesRegex(ValueError, "Solana-only"):
            _validate_discover_candidates_args(_args(chain="ethereum"))


# ---------------------------------------------------------------------------
# C. Candidate-stage reporting separation
# ---------------------------------------------------------------------------

class TestCandidateStageReporting(unittest.TestCase):

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.addCleanup(temp_dir.cleanup)
        self.db_path = pathlib.Path(temp_dir.name) / "v2-2h1-stage-reporting.sqlite3"
        apply_migrations(self.db_path)

    def _run_args(self, **overrides):
        values = {
            "db_path": str(self.db_path),
            "project_root": str(PROJECT_ROOT),
            "format": "json",
            "no_color": True,
            "operator_approved": True,
            "chain": "solana",
            "max_candidates": 10,
            "query": "pump",
            "timeout_seconds": 5.0,
            "source_name": "dexscreener",
            "request_key": "v2-2h1-test-discovery",
        }
        values.update(overrides)
        return argparse.Namespace(**values)

    def test_candidate_stage_report_present(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=_success_transport
        )
        self.assertIn("candidate_stage_report", payload)
        report = payload["candidate_stage_report"]
        for key in (
            "candidates_seen_total",
            "candidates_normalized_total",
            "candidates_persisted_total",
            "candidates_rejected_pre_persistence",
            "candidates_considered_for_selection",
            "candidates_selected",
            "candidates_rejected_by_selection",
        ):
            self.assertIn(key, report)

    def test_seen_and_normalized_match_and_are_measured(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=_success_transport
        )
        report = payload["candidate_stage_report"]
        self.assertEqual(report["candidates_seen_total"], 2)
        self.assertEqual(report["candidates_normalized_total"], 2)

    def test_persisted_and_rejected_pre_persistence_measured(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(max_candidates=1), transport=_success_transport
        )
        report = payload["candidate_stage_report"]
        # With a cap of 1, one candidate persists and the other is rejected
        # pre-persistence purely because the cap was reached.
        self.assertEqual(report["candidates_persisted_total"], 1)
        self.assertEqual(report["candidates_rejected_pre_persistence"], 1)
        self.assertEqual(payload["candidates_accepted"], report["candidates_persisted_total"])
        self.assertEqual(payload["candidates_rejected"], report["candidates_rejected_pre_persistence"])

    def test_wider_cap_persists_more_than_old_hardcoded_ceiling(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(max_candidates=10), transport=_success_transport
        )
        report = payload["candidate_stage_report"]
        # Both fixture candidates persist because the cap (10) now exceeds
        # the old hardcoded ceiling (3) as well as the fixture size (2).
        self.assertEqual(report["candidates_persisted_total"], 2)
        self.assertEqual(report["candidates_rejected_pre_persistence"], 0)

    def test_selection_stage_fields_are_not_measured(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=_success_transport
        )
        report = payload["candidate_stage_report"]
        # This command does not invoke V2-2C selection-batch logic, so these
        # must be explicitly NOT_MEASURED rather than guessed or omitted.
        self.assertEqual(report["candidates_considered_for_selection"], "NOT_MEASURED")
        self.assertEqual(report["candidates_selected"], "NOT_MEASURED")
        self.assertEqual(report["candidates_rejected_by_selection"], "NOT_MEASURED")

    def test_rejection_reasons_remain_visible(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(max_candidates=1), transport=_success_transport
        )
        self.assertEqual(len(payload["rejected_candidates"]), 1)
        self.assertIn("reject_reason", payload["rejected_candidates"][0])
        self.assertEqual(
            payload["rejected_candidates"][0]["reject_reason"], "max_candidates_reached"
        )

    def test_stage_report_values_are_categorical_not_scored(self):
        payload = build_discover_candidates_once_payload(
            self._run_args(), transport=_success_transport
        )
        report = payload["candidate_stage_report"]
        for key, value in report.items():
            with self.subTest(key=key):
                self.assertTrue(
                    isinstance(value, int) or value == "NOT_MEASURED",
                    f"{key} must be an int count or the literal 'NOT_MEASURED', got {value!r}",
                )
                if isinstance(value, int):
                    self.assertNotIsInstance(value, bool)


# ---------------------------------------------------------------------------
# D. Selection-batch schema readiness check
# ---------------------------------------------------------------------------

class TestSelectionBatchSchemaReadiness(unittest.TestCase):

    def test_passes_when_schema_fully_applied(self):
        db_path = _fresh_db_with_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        # Must not raise.
        check_selection_batch_schema_ready(db_path)

    def test_passes_with_open_connection(self):
        db_path = _fresh_db_with_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        conn = sqlite3.connect(db_path)
        try:
            check_selection_batch_schema_ready(conn)
        finally:
            conn.close()

    def test_fails_when_both_tables_missing(self):
        db_path = _fresh_db_without_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        with self.assertRaises(SelectionBatchSchemaNotReadyError) as ctx:
            check_selection_batch_schema_ready(db_path)
        message = str(ctx.exception)
        self.assertIn("printer_selection_batches", message)
        self.assertIn("printer_selection_batch_items", message)
        self.assertIn("025_selection_batch.sql", message)

    def test_fails_when_selection_batch_items_missing(self):
        db_path = _fresh_db_without_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        conn = sqlite3.connect(db_path)
        conn.execute(
            """
            CREATE TABLE printer_selection_batches (
                id INTEGER PRIMARY KEY,
                batch_id TEXT,
                batch_status TEXT,
                window_kind TEXT,
                candidate_pool_total INTEGER,
                selected_count INTEGER,
                rejected_count INTEGER,
                unavailable_or_unclassified_count INTEGER,
                pool_summary_json TEXT,
                pool_diversity_notes TEXT,
                pool_quality_notes TEXT,
                operator_approved INTEGER
            )
            """
        )
        conn.commit()
        conn.close()
        with self.assertRaises(SelectionBatchSchemaNotReadyError) as ctx:
            check_selection_batch_schema_ready(db_path)
        message = str(ctx.exception)
        self.assertIn("printer_selection_batch_items", message)
        self.assertIn("missing table(s)", message)

    def test_fails_when_critical_column_missing(self):
        db_path = _fresh_db_with_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        conn = sqlite3.connect(db_path)
        conn.execute("ALTER TABLE printer_selection_batch_items RENAME TO printer_selection_batch_items_old")
        conn.execute(
            """
            CREATE TABLE printer_selection_batch_items (
                id INTEGER PRIMARY KEY,
                batch_id TEXT NOT NULL
            )
            """
        )
        conn.commit()
        conn.close()
        with self.assertRaises(SelectionBatchSchemaNotReadyError) as ctx:
            check_selection_batch_schema_ready(db_path)
        message = str(ctx.exception)
        self.assertIn("primary_bucket", message)

    def test_readiness_check_does_not_mutate_database(self):
        db_path = _fresh_db_without_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        conn = sqlite3.connect(db_path)
        before_tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()

        with self.assertRaises(SelectionBatchSchemaNotReadyError):
            check_selection_batch_schema_ready(db_path)

        conn = sqlite3.connect(db_path)
        try:
            after_tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        finally:
            conn.close()
        self.assertEqual(before_tables, after_tables)

    def test_readiness_check_uses_read_only_connection_for_path_input(self):
        db_path = _fresh_db_with_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        # Passing a path (not an existing connection) must not leave a
        # writable connection open or write anything -- verified indirectly
        # by confirming the row count of both tables is unchanged before and
        # after the check.
        conn = sqlite3.connect(db_path)
        before = (
            conn.execute("SELECT COUNT(*) FROM printer_selection_batches").fetchone()[0],
            conn.execute("SELECT COUNT(*) FROM printer_selection_batch_items").fetchone()[0],
        )
        conn.close()

        check_selection_batch_schema_ready(db_path)

        conn = sqlite3.connect(db_path)
        try:
            after = (
                conn.execute("SELECT COUNT(*) FROM printer_selection_batches").fetchone()[0],
                conn.execute("SELECT COUNT(*) FROM printer_selection_batch_items").fetchone()[0],
            )
        finally:
            conn.close()
        self.assertEqual(before, after)

    def test_persist_selection_batch_fails_fast_when_schema_missing(self):
        db_path = _fresh_db_without_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        with self.assertRaises(SelectionBatchSchemaNotReadyError):
            persist_selection_batch(
                db_path,
                batch_id="v2-2h1-test-batch",
                items=[],
                universe_summary={},
            )

    def test_persist_selection_batch_still_succeeds_when_schema_ready(self):
        db_path = _fresh_db_with_migrations()
        self.addCleanup(lambda: db_path.unlink(missing_ok=True))
        result = persist_selection_batch(
            db_path,
            batch_id="v2-2h1-test-batch-ready",
            items=[],
            universe_summary={},
        )
        self.assertEqual(result["batch_id"], "v2-2h1-test-batch-ready")
        self.assertEqual(result["total_items"], 0)


if __name__ == "__main__":
    unittest.main()
