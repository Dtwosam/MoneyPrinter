"""
Post-Lane 10 Lane E2C-C -- Active Cycle Readiness Package

Tests prove:
- e2c_readiness module imports cleanly and all exports are present
- HARD_LOCKS contains all required keys, all values are False
- token list validation: valid 1-token and 2-token cases
- token list validation: reject 0 tokens, >2 tokens, duplicates, bad format, bad lane
- DB preflight: missing path, missing DB, backup not confirmed, running jobs, active locks
- DB preflight: clean DB passes
- source budget allowed when no recent requests
- source budget blocked when rate exceeded (uses E2C-B count_recent_source_requests helper)
- cycle plan includes correct job kinds per lifecycle lane
- cycle plan always includes MEMORY_WINDOW_CLOSE
- cycle plan caps are correct
- full payload recommendation: BLOCKED / LIMITED_GO_FOR_OPERATOR_REVIEW
- output is JSON-serializable
- no DB mutation
- no source fetching (no HTTP libraries imported)
- no paper decisions / BUY / SELL / HOLD / positions / PnL
- CLI command main_plan_bounded_15m_memory_factory_cycle returns 0 and outputs JSON
- pyproject.toml entry point is registered
"""

import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from unittest.mock import patch

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import main_plan_bounded_15m_memory_factory_cycle
from printer_v1.operator_cli.e2c_readiness import (
    HARD_LOCKS,
    MAX_ACTIVE_TOKENS,
    MAX_TOKEN_COUNT,
    MAX_TRACK_FAST,
    MAX_TRACK_NORMAL,
    MIN_TOKEN_COUNT,
    RECOMMENDATION_BLOCKED,
    RECOMMENDATION_LIMITED_GO,
    SOLANA_BASE58_ALPHABET,
    VALID_LIFECYCLE_LANES,
    build_cycle_plan,
    build_e2c_readiness_payload,
    check_db_preflight,
    is_valid_solana_mint,
    plan_source_budget,
    validate_token_list,
)
from printer_v1.sources.contracts import NormalizedSourceResult, build_governed_source_request
from printer_v1.sources.recording import record_source_request, record_source_response
from printer_v1.sources.registry import SOURCE_REGISTRY


# Structurally valid Solana base58 test mints (synthetic -- not real token addresses).
_MINT_A = "A" * 43  # 43 chars, all 'A' which is in base58
_MINT_B = "B" * 44  # 44 chars, all 'B' which is in base58

_RATE_LIMIT_SOURCE = "alternative_me"
_RATE_LIMIT_KIND = "fear_greed_context"
_RATE_LIMIT = SOURCE_REGISTRY[_RATE_LIMIT_SOURCE].default_rate_limit_per_minute


class _DbTestBase(unittest.TestCase):
    """Temp SQLite with all migrations applied. Cleaned up after each test."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2c_c_test.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()

    def _insert_scheduler_job(self, *, status: str, locked_at: str | None = None) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO printer_scheduler_jobs"
                " (job_name, job_kind, status, scheduled_for)"
                " VALUES (?, ?, ?, ?)",
                ("e2c_c_test_job", "TRACK_FAST_FIRST_15M", status, "2026-06-27T12:00:00"),
            )
            if locked_at is not None:
                conn.execute(
                    "UPDATE printer_scheduler_jobs SET locked_at = ?"
                    " WHERE job_name = 'e2c_c_test_job'",
                    (locked_at,),
                )
            conn.commit()
        finally:
            conn.close()

    def _record_success_attempt(self, source_name: str, request_kind: str) -> None:
        # No fixed timestamp -- use real current time so count_recent_source_requests
        # (which also uses the real clock) finds these records within its 60-second window.
        req = build_governed_source_request(source_name, request_kind)
        req_record = record_source_request(self.db_path, req)
        normalized = NormalizedSourceResult(
            source_name=source_name,
            request_kind=request_kind,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            normalized_payload={},
            status_code=200,
        )
        record_source_response(self.db_path, req_record, normalized)


# ---------------------------------------------------------------------------
# Import and constant tests
# ---------------------------------------------------------------------------

class LaneE2CCImportTests(unittest.TestCase):
    """Prove e2c_readiness module imports cleanly and constants are set."""

    def test_e2c_readiness_module_importable(self):
        import printer_v1.operator_cli.e2c_readiness as mod
        self.assertIsNotNone(mod)

    def test_commands_main_function_importable(self):
        self.assertTrue(callable(main_plan_bounded_15m_memory_factory_cycle))

    def test_solana_base58_alphabet_excludes_zero(self):
        self.assertNotIn("0", SOLANA_BASE58_ALPHABET)

    def test_solana_base58_alphabet_excludes_capital_O(self):
        self.assertNotIn("O", SOLANA_BASE58_ALPHABET)

    def test_solana_base58_alphabet_excludes_capital_I(self):
        self.assertNotIn("I", SOLANA_BASE58_ALPHABET)

    def test_solana_base58_alphabet_excludes_lowercase_l(self):
        self.assertNotIn("l", SOLANA_BASE58_ALPHABET)

    def test_valid_lifecycle_lanes_contains_track_fast(self):
        self.assertIn("TRACK_FAST", VALID_LIFECYCLE_LANES)

    def test_valid_lifecycle_lanes_contains_track_normal(self):
        self.assertIn("TRACK_NORMAL", VALID_LIFECYCLE_LANES)

    def test_min_token_count_is_1(self):
        self.assertEqual(MIN_TOKEN_COUNT, 1)

    def test_max_token_count_is_2(self):
        self.assertEqual(MAX_TOKEN_COUNT, 2)

    def test_max_active_tokens_is_10(self):
        self.assertEqual(MAX_ACTIVE_TOKENS, 10)

    def test_max_track_fast_is_3(self):
        self.assertEqual(MAX_TRACK_FAST, 3)

    def test_max_track_normal_is_7(self):
        self.assertEqual(MAX_TRACK_NORMAL, 7)

    def test_recommendation_blocked_value(self):
        self.assertEqual(RECOMMENDATION_BLOCKED, "BLOCKED")

    def test_recommendation_limited_go_value(self):
        self.assertEqual(RECOMMENDATION_LIMITED_GO, "LIMITED_GO_FOR_OPERATOR_REVIEW")

    def test_no_http_libraries_imported_by_module(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(
                lib,
                sys.modules,
                f"Network library {lib!r} must not be imported by e2c_readiness",
            )

    def test_pyproject_entry_point_registered(self):
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn(
            "printer-plan-bounded-15m-memory-factory-cycle",
            content,
        )
        self.assertIn(
            "main_plan_bounded_15m_memory_factory_cycle",
            content,
        )


# ---------------------------------------------------------------------------
# Hard lock tests
# ---------------------------------------------------------------------------

class LaneE2CCHardLockTests(unittest.TestCase):
    """Prove all hard lock flags are present and False."""

    _EXPECTED_LOCKS = [
        "source_fetching_enabled",
        "scheduler_execution_enabled",
        "snapshot_creation_enabled",
        "memory_creation_enabled",
        "retrieval_activation_enabled",
        "paper_decisions_enabled",
        "buy_enabled",
        "sell_enabled",
        "hold_enabled",
        "positions_enabled",
        "pnl_enabled",
    ]

    def test_hard_locks_has_all_required_keys(self):
        for key in self._EXPECTED_LOCKS:
            self.assertIn(key, HARD_LOCKS, f"HARD_LOCKS missing key: {key!r}")

    def test_all_hard_lock_values_are_false(self):
        for key, val in HARD_LOCKS.items():
            self.assertIs(val, False, f"HARD_LOCKS[{key!r}] must be False; got {val!r}")

    def test_all_hard_lock_values_are_python_bool(self):
        for key, val in HARD_LOCKS.items():
            self.assertIsInstance(val, bool, f"HARD_LOCKS[{key!r}] must be bool; got {type(val)}")

    def test_source_fetching_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["source_fetching_enabled"], False)

    def test_scheduler_execution_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["scheduler_execution_enabled"], False)

    def test_snapshot_creation_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["snapshot_creation_enabled"], False)

    def test_memory_creation_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["memory_creation_enabled"], False)

    def test_retrieval_activation_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["retrieval_activation_enabled"], False)

    def test_paper_decisions_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["paper_decisions_enabled"], False)

    def test_buy_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["buy_enabled"], False)

    def test_sell_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["sell_enabled"], False)

    def test_hold_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["hold_enabled"], False)

    def test_positions_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["positions_enabled"], False)

    def test_pnl_enabled_is_false(self):
        self.assertIs(HARD_LOCKS["pnl_enabled"], False)


# ---------------------------------------------------------------------------
# Token mint format validation
# ---------------------------------------------------------------------------

class LaneE2CCMintValidationTests(unittest.TestCase):
    """Prove is_valid_solana_mint correctly accepts and rejects addresses."""

    def test_valid_mint_43_chars(self):
        self.assertTrue(is_valid_solana_mint(_MINT_A))

    def test_valid_mint_44_chars(self):
        self.assertTrue(is_valid_solana_mint(_MINT_B))

    def test_invalid_mint_too_short(self):
        self.assertFalse(is_valid_solana_mint("A" * 42))

    def test_invalid_mint_too_long(self):
        self.assertFalse(is_valid_solana_mint("A" * 45))

    def test_invalid_mint_contains_zero(self):
        self.assertFalse(is_valid_solana_mint("0" + "A" * 42))

    def test_invalid_mint_contains_capital_O(self):
        self.assertFalse(is_valid_solana_mint("O" + "A" * 42))

    def test_invalid_mint_contains_capital_I(self):
        self.assertFalse(is_valid_solana_mint("I" + "A" * 42))

    def test_invalid_mint_contains_lowercase_l(self):
        self.assertFalse(is_valid_solana_mint("l" + "A" * 42))

    def test_invalid_mint_empty_string(self):
        self.assertFalse(is_valid_solana_mint(""))

    def test_invalid_mint_non_string(self):
        self.assertFalse(is_valid_solana_mint(None))  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Token list validation
# ---------------------------------------------------------------------------

class LaneE2CCTokenValidationTests(unittest.TestCase):
    """Prove validate_token_list accepts and rejects token lists correctly."""

    def test_valid_single_token_track_fast(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]
        result = validate_token_list(tokens)
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["token_count"], 1)
        self.assertEqual(len(result["tokens"]), 1)
        self.assertEqual(result["tokens"][0]["lifecycle_lane"], "TRACK_FAST")

    def test_valid_single_token_track_normal(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_NORMAL"}]
        result = validate_token_list(tokens)
        self.assertTrue(result["valid"])
        self.assertEqual(result["token_count"], 1)

    def test_valid_two_token_mixed_track_fast_and_normal(self):
        tokens = [
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
            {"token_mint": _MINT_B, "lifecycle_lane": "TRACK_NORMAL"},
        ]
        result = validate_token_list(tokens)
        self.assertTrue(result["valid"])
        self.assertEqual(result["token_count"], 2)
        self.assertEqual(len(result["tokens"]), 2)

    def test_reject_zero_tokens(self):
        result = validate_token_list([])
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)
        self.assertIn("at least", result["errors"][0])

    def test_reject_more_than_two_tokens(self):
        tokens = [
            {"token_mint": "A" * 43, "lifecycle_lane": "TRACK_FAST"},
            {"token_mint": "B" * 44, "lifecycle_lane": "TRACK_NORMAL"},
            {"token_mint": "C" * 43, "lifecycle_lane": "TRACK_FAST"},
        ]
        result = validate_token_list(tokens)
        self.assertFalse(result["valid"])
        self.assertIn("at most", result["errors"][0])

    def test_reject_duplicate_token_mints(self):
        tokens = [
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_NORMAL"},
        ]
        result = validate_token_list(tokens)
        self.assertFalse(result["valid"])
        duplicate_errors = [e for e in result["errors"] if "duplicate" in e]
        self.assertGreater(len(duplicate_errors), 0)

    def test_reject_invalid_token_mint_format_too_short(self):
        tokens = [{"token_mint": "A" * 10, "lifecycle_lane": "TRACK_FAST"}]
        result = validate_token_list(tokens)
        self.assertFalse(result["valid"])
        self.assertTrue(any("not a valid Solana base58 mint" in e for e in result["errors"]))

    def test_reject_invalid_token_mint_format_bad_chars(self):
        tokens = [{"token_mint": "0" + "A" * 42, "lifecycle_lane": "TRACK_FAST"}]
        result = validate_token_list(tokens)
        self.assertFalse(result["valid"])
        self.assertTrue(any("not a valid Solana base58 mint" in e for e in result["errors"]))

    def test_reject_unsupported_lifecycle_lane(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "UNKNOWN_LANE"}]
        result = validate_token_list(tokens)
        self.assertFalse(result["valid"])
        self.assertTrue(any("not supported" in e for e in result["errors"]))

    def test_tokens_list_empty_when_invalid(self):
        result = validate_token_list([])
        self.assertEqual(result["tokens"], [])

    def test_tokens_list_populated_when_valid(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]
        result = validate_token_list(tokens)
        self.assertEqual(len(result["tokens"]), 1)
        self.assertEqual(result["tokens"][0]["token_mint"], _MINT_A)

    def test_multiple_errors_collected_for_two_bad_tokens(self):
        tokens = [
            {"token_mint": "bad!", "lifecycle_lane": "BOGUS"},
            {"token_mint": "bad!", "lifecycle_lane": "BOGUS"},
        ]
        result = validate_token_list(tokens)
        self.assertFalse(result["valid"])
        # expects duplicate + bad mint + bad lane errors
        self.assertGreater(len(result["errors"]), 2)


# ---------------------------------------------------------------------------
# DB preflight tests
# ---------------------------------------------------------------------------

class LaneE2CCDbPreflightTests(_DbTestBase):
    """Prove check_db_preflight reports correctly without mutating the DB."""

    def test_no_db_path_reports_preflight_failed(self):
        result = check_db_preflight(None, backup_confirmed=True)
        self.assertFalse(result["preflight_passed"])
        self.assertIsNone(result["db_path"])
        self.assertFalse(result["db_path_exists"])
        self.assertGreater(len(result["errors"]), 0)

    def test_missing_db_file_reports_path_not_exist(self):
        missing = pathlib.Path(self.tempdir.name) / "nonexistent.sqlite3"
        result = check_db_preflight(missing, backup_confirmed=True)
        self.assertFalse(result["preflight_passed"])
        self.assertFalse(result["db_path_exists"])

    def test_backup_not_confirmed_reports_blocked(self):
        result = check_db_preflight(self.db_path, backup_confirmed=False)
        self.assertFalse(result["preflight_passed"])
        self.assertFalse(result["backup_confirmed"])
        self.assertTrue(any("backup" in e.lower() for e in result["errors"]))

    def test_clean_db_with_backup_confirmed_passes(self):
        result = check_db_preflight(self.db_path, backup_confirmed=True)
        self.assertTrue(result["db_path_exists"])
        self.assertTrue(result["backup_confirmed"])
        self.assertEqual(result["running_jobs"], 0)
        self.assertEqual(result["active_locks"], 0)
        self.assertTrue(result["preflight_passed"])
        self.assertEqual(result["errors"], [])

    def test_running_jobs_block_readiness(self):
        self._insert_scheduler_job(status="RUNNING")
        result = check_db_preflight(self.db_path, backup_confirmed=True)
        self.assertFalse(result["preflight_passed"])
        self.assertEqual(result["running_jobs"], 1)
        self.assertTrue(any("RUNNING" in e for e in result["errors"]))

    def test_active_locks_block_readiness(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        result = check_db_preflight(self.db_path, backup_confirmed=True)
        self.assertFalse(result["preflight_passed"])
        self.assertEqual(result["active_locks"], 1)
        self.assertTrue(any("lock" in e for e in result["errors"]))
    def test_lock_owner_without_locked_at_blocks_readiness(self):
        self._insert_scheduler_job(status="PENDING")
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE printer_scheduler_jobs SET lock_owner = ?"
                " WHERE job_name = 'e2c_c_test_job'",
                ("e2c_c_stale_owner",),
            )
            conn.commit()
        finally:
            conn.close()

        result = check_db_preflight(self.db_path, backup_confirmed=True)
        self.assertFalse(result["preflight_passed"])
        self.assertEqual(result["active_locks"], 1)
        self.assertTrue(any("lock" in e for e in result["errors"]))

    def test_preflight_does_not_mutate_db(self):
        before = self._count_rows("printer_scheduler_jobs")
        check_db_preflight(self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_scheduler_jobs")
        self.assertEqual(before, after)

    def test_db_path_returned_as_string(self):
        result = check_db_preflight(self.db_path, backup_confirmed=True)
        self.assertIsInstance(result["db_path"], str)

    def test_running_jobs_and_active_locks_none_when_db_missing(self):
        missing = pathlib.Path(self.tempdir.name) / "nonexistent.sqlite3"
        result = check_db_preflight(missing, backup_confirmed=True)
        self.assertIsNone(result["running_jobs"])
        self.assertIsNone(result["active_locks"])


# ---------------------------------------------------------------------------
# Source budget tests
# ---------------------------------------------------------------------------

class LaneE2CCSourceBudgetTests(_DbTestBase):
    """Prove plan_source_budget reports correctly using E2C-B budget helper."""

    def test_source_budget_allowed_when_no_recent_requests(self):
        result = plan_source_budget(self.db_path)
        self.assertTrue(result["all_sources_allowed"])
        self.assertGreater(result["total_sources"], 0)
        self.assertEqual(result["allowed_count"], result["total_sources"])

    def test_source_budget_no_db_assumes_zero_counts(self):
        result = plan_source_budget(None)
        self.assertTrue(result["all_sources_allowed"])
        for src in result["planned_sources"]:
            self.assertEqual(src["recent_request_count"], 0)

    def test_planned_sources_only_include_non_paid_sources(self):
        result = plan_source_budget(None)
        paid_sources = {
            name for name, defn in SOURCE_REGISTRY.items() if defn.requires_paid_plan
        }
        reported_names = {s["source_name"] for s in result["planned_sources"]}
        self.assertTrue(paid_sources.isdisjoint(reported_names))

    def test_each_source_entry_has_required_fields(self):
        result = plan_source_budget(None)
        for src in result["planned_sources"]:
            self.assertIn("source_name", src)
            self.assertIn("recent_request_count", src)
            self.assertIn("rate_limit_per_minute", src)
            self.assertIn("governor_decision", src)
            self.assertIn("allowed", src)

    def test_source_budget_blocked_when_rate_exceeded_using_e2c_b_helper(self):
        # Insert _RATE_LIMIT consumed attempts for alternative_me (limit=10).
        # E2C-B's count_recent_source_requests will count these as consumed.
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)

        result = plan_source_budget(self.db_path)

        alt_me = next(
            s for s in result["planned_sources"] if s["source_name"] == _RATE_LIMIT_SOURCE
        )
        self.assertFalse(alt_me["allowed"])
        self.assertEqual(alt_me["governor_decision"], "rate_limit_exceeded")
        self.assertEqual(alt_me["recent_request_count"], _RATE_LIMIT)
        self.assertFalse(result["all_sources_allowed"])

    def test_source_budget_does_not_fetch_sources(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(
                lib,
                sys.modules,
                f"plan_source_budget must not import {lib!r}",
            )

    def test_budget_summary_string_is_present(self):
        result = plan_source_budget(None)
        self.assertIn("budget_summary", result)
        self.assertIn("sources allowed by Source Governor", result["budget_summary"])

    def test_source_budget_does_not_mutate_db(self):
        before = {
            t: self._count_rows(t)
            for t in ("printer_source_requests", "printer_source_responses", "printer_source_failures")
        }
        plan_source_budget(self.db_path)
        after = {
            t: self._count_rows(t)
            for t in ("printer_source_requests", "printer_source_responses", "printer_source_failures")
        }
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# Cycle plan tests
# ---------------------------------------------------------------------------

class LaneE2CCCyclePlanTests(unittest.TestCase):
    """Prove build_cycle_plan produces correct job kinds."""

    def test_single_track_fast_plans_correct_job_kind(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]
        result = build_cycle_plan(tokens)
        job_kinds = [j["job_kind"] for j in result["planned_jobs"]]
        self.assertIn("TRACK_FAST_FIRST_15M", job_kinds)

    def test_single_track_normal_plans_correct_job_kind(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_NORMAL"}]
        result = build_cycle_plan(tokens)
        job_kinds = [j["job_kind"] for j in result["planned_jobs"]]
        self.assertIn("TRACK_NORMAL_FIRST_15M", job_kinds)

    def test_two_token_mixed_plans_both_job_kinds(self):
        tokens = [
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
            {"token_mint": _MINT_B, "lifecycle_lane": "TRACK_NORMAL"},
        ]
        result = build_cycle_plan(tokens)
        job_kinds = [j["job_kind"] for j in result["planned_jobs"]]
        self.assertIn("TRACK_FAST_FIRST_15M", job_kinds)
        self.assertIn("TRACK_NORMAL_FIRST_15M", job_kinds)

    def test_memory_window_close_always_included(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]
        result = build_cycle_plan(tokens)
        job_kinds = [j["job_kind"] for j in result["planned_jobs"]]
        self.assertIn("MEMORY_WINDOW_CLOSE", job_kinds)

    def test_memory_window_close_included_even_with_no_tokens(self):
        result = build_cycle_plan([])
        job_kinds = [j["job_kind"] for j in result["planned_jobs"]]
        self.assertIn("MEMORY_WINDOW_CLOSE", job_kinds)

    def test_track_fast_job_has_correct_token_mint(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]
        result = build_cycle_plan(tokens)
        fast_jobs = [j for j in result["planned_jobs"] if j["job_kind"] == "TRACK_FAST_FIRST_15M"]
        self.assertEqual(len(fast_jobs), 1)
        self.assertEqual(fast_jobs[0]["token_mint"], _MINT_A)

    def test_max_active_tokens_cap(self):
        result = build_cycle_plan([])
        self.assertEqual(result["max_active_tokens"], MAX_ACTIVE_TOKENS)

    def test_max_track_fast_cap(self):
        result = build_cycle_plan([])
        self.assertEqual(result["max_track_fast"], MAX_TRACK_FAST)

    def test_max_track_normal_cap(self):
        result = build_cycle_plan([])
        self.assertEqual(result["max_track_normal"], MAX_TRACK_NORMAL)

    def test_first_cycle_token_cap_is_2(self):
        result = build_cycle_plan([])
        self.assertEqual(result["first_cycle_token_cap"], MAX_TOKEN_COUNT)

    def test_zero_clean_memories_allowed_is_true(self):
        result = build_cycle_plan([])
        self.assertTrue(result["zero_clean_memories_allowed"])

    def test_paper_decisions_disabled_in_plan(self):
        result = build_cycle_plan([])
        self.assertFalse(result["paper_decisions_enabled"])

    def test_memory_window_close_has_null_token_mint(self):
        result = build_cycle_plan([])
        close_jobs = [j for j in result["planned_jobs"] if j["job_kind"] == "MEMORY_WINDOW_CLOSE"]
        self.assertEqual(len(close_jobs), 1)
        self.assertIsNone(close_jobs[0]["token_mint"])


# ---------------------------------------------------------------------------
# Full payload integration tests
# ---------------------------------------------------------------------------

class LaneE2CCPayloadIntegrationTests(_DbTestBase):
    """Prove build_e2c_readiness_payload produces a correct, JSON-serializable payload."""

    def _valid_tokens(self):
        return [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]

    def test_payload_is_json_serializable_with_valid_inputs(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        serialized = json.dumps(payload)
        self.assertIsInstance(serialized, str)
        parsed = json.loads(serialized)
        self.assertEqual(parsed["command"], "printer-plan-bounded-15m-memory-factory-cycle")

    def test_command_name_is_correct(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["command"], "printer-plan-bounded-15m-memory-factory-cycle")

    def test_dry_run_is_true(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertIs(payload["dry_run"], True)

    def test_recommendation_limited_go_with_valid_inputs(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_LIMITED_GO)

    def test_recommendation_blocked_no_token_list(self):
        payload = build_e2c_readiness_payload([], self.db_path, backup_confirmed=True)
        self.assertEqual(payload["recommendation"], RECOMMENDATION_BLOCKED)

    def test_recommendation_blocked_backup_not_confirmed(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=False
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_BLOCKED)

    def test_recommendation_blocked_missing_db_path(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), None, backup_confirmed=True
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_BLOCKED)

    def test_recommendation_blocked_running_jobs(self):
        self._insert_scheduler_job(status="RUNNING")
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_BLOCKED)

    def test_recommendation_blocked_active_locks(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_BLOCKED)

    def test_hard_locks_all_false_in_payload(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"payload hard_locks[{key!r}] must be False")

    def test_no_paper_decisions_in_payload(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertFalse(payload["hard_locks"]["paper_decisions_enabled"])
        self.assertFalse(payload["cycle_plan"]["paper_decisions_enabled"])

    def test_no_buy_sell_hold_in_payload(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertFalse(payload["hard_locks"]["buy_enabled"])
        self.assertFalse(payload["hard_locks"]["sell_enabled"])
        self.assertFalse(payload["hard_locks"]["hold_enabled"])

    def test_no_positions_or_pnl_in_payload(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertFalse(payload["hard_locks"]["positions_enabled"])
        self.assertFalse(payload["hard_locks"]["pnl_enabled"])

    def test_no_db_mutation(self):
        tables = (
            "printer_scheduler_jobs",
            "printer_source_requests",
            "printer_source_responses",
            "printer_source_failures",
        )
        before = {t: self._count_rows(t) for t in tables}
        build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        after = {t: self._count_rows(t) for t in tables}
        self.assertEqual(before, after)

    def test_no_source_fetching_after_payload_build(self):
        build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(lib, sys.modules, f"{lib!r} must not be imported")

    def test_payload_has_all_top_level_sections(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        for key in (
            "command", "dry_run", "token_list_validation", "db_preflight",
            "source_budget", "cycle_plan", "hard_locks",
            "recommendation", "recommendation_reasons",
        ):
            self.assertIn(key, payload, f"payload missing key: {key!r}")

    def test_recommendation_reasons_is_list(self):
        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertIsInstance(payload["recommendation_reasons"], list)
        self.assertGreater(len(payload["recommendation_reasons"]), 0)

    def test_source_budget_blocked_case_in_full_payload(self):
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)

        payload = build_e2c_readiness_payload(
            self._valid_tokens(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_BLOCKED)
        self.assertFalse(payload["source_budget"]["all_sources_allowed"])


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------

class LaneE2CCCliTests(_DbTestBase):
    """Prove the CLI command produces valid JSON output and returns 0."""

    def test_cli_valid_one_token_track_fast_returns_0(self):
        argv = [
            "--token", f"{_MINT_A}:TRACK_FAST",
            "--backup-confirmed",
            "--db-path", str(self.db_path),
        ]
        with patch("sys.stdout", new_callable=io.StringIO):
            result = main_plan_bounded_15m_memory_factory_cycle(argv)
        self.assertEqual(result, 0)

    def test_cli_valid_two_token_mixed_returns_0(self):
        argv = [
            "--token", f"{_MINT_A}:TRACK_FAST",
            "--token", f"{_MINT_B}:TRACK_NORMAL",
            "--backup-confirmed",
            "--db-path", str(self.db_path),
        ]
        with patch("sys.stdout", new_callable=io.StringIO):
            result = main_plan_bounded_15m_memory_factory_cycle(argv)
        self.assertEqual(result, 0)

    def test_cli_output_is_valid_json(self):
        argv = [
            "--token", f"{_MINT_A}:TRACK_FAST",
            "--backup-confirmed",
            "--db-path", str(self.db_path),
        ]
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            main_plan_bounded_15m_memory_factory_cycle(argv)
        output = buf.getvalue()
        parsed = json.loads(output)
        self.assertEqual(parsed["command"], "printer-plan-bounded-15m-memory-factory-cycle")

    def test_cli_output_contains_dry_run_true(self):
        argv = [
            "--token", f"{_MINT_A}:TRACK_FAST",
            "--backup-confirmed",
            "--db-path", str(self.db_path),
        ]
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            main_plan_bounded_15m_memory_factory_cycle(argv)
        parsed = json.loads(buf.getvalue())
        self.assertIs(parsed["dry_run"], True)

    def test_cli_no_token_still_returns_0_with_blocked_recommendation(self):
        argv = [
            "--backup-confirmed",
            "--db-path", str(self.db_path),
        ]
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            result = main_plan_bounded_15m_memory_factory_cycle(argv)
        self.assertEqual(result, 0)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["recommendation"], RECOMMENDATION_BLOCKED)

    def test_cli_without_backup_confirmed_outputs_blocked(self):
        argv = [
            "--token", f"{_MINT_A}:TRACK_FAST",
            "--db-path", str(self.db_path),
        ]
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            main_plan_bounded_15m_memory_factory_cycle(argv)
        parsed = json.loads(buf.getvalue())
        self.assertEqual(parsed["recommendation"], RECOMMENDATION_BLOCKED)

    def test_cli_hard_locks_all_false_in_json_output(self):
        argv = [
            "--token", f"{_MINT_A}:TRACK_FAST",
            "--backup-confirmed",
            "--db-path", str(self.db_path),
        ]
        buf = io.StringIO()
        with patch("sys.stdout", new=buf):
            main_plan_bounded_15m_memory_factory_cycle(argv)
        parsed = json.loads(buf.getvalue())
        for key, val in parsed["hard_locks"].items():
            self.assertFalse(val, f"CLI output hard_locks[{key!r}] must be false")


if __name__ == "__main__":
    unittest.main()
