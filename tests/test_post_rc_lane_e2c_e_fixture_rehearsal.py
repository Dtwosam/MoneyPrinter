"""
Post-Lane 10 Lane E2C-E -- Fixture Rehearsal Package

Tests prove:
- e2c_fixture_rehearsal module imports cleanly and exports are present
- RECOMMENDATION_FIXTURE_PASS constant is correct
- pyproject.toml entry point is registered
- valid 1-token TRACK_FAST fixture rehearsal produces FIXTURE_REHEARSAL_PASS
- valid 2-token mixed TRACK_FAST/TRACK_NORMAL fixture rehearsal produces FIXTURE_REHEARSAL_PASS
- reject 0 tokens (BLOCKED)
- reject more than 2 tokens (BLOCKED)
- reject duplicate mints (BLOCKED)
- reject invalid mint format (BLOCKED)
- reject unsupported lifecycle lane (BLOCKED)
- missing DB blocks (BLOCKED)
- backup not confirmed blocks (BLOCKED)
- RUNNING job blocks (BLOCKED)
- locked_at active lock blocks (BLOCKED)
- lock_owner active lock blocks (BLOCKED)
- source budget rate-limit-exceeded blocks (BLOCKED)
- planned job kinds are correct (TRACK_FAST_FIRST_15M, TRACK_NORMAL_FIRST_15M, MEMORY_WINDOW_CLOSE)
- fixture evidence plan exists and is fixture_only
- synthetic_evidence_only is true in each evidence plan entry
- no DB mutation across all checked tables
- optional missing tables are reported safely as table_missing
- all 11 hard-lock flags are False in payload
- payload is JSON-serializable
- CLI command outputs JSON
- no source fetching libraries imported
- no paper decisions / BUY / SELL / HOLD / positions / PnL in module
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

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import main_rehearse_bounded_15m_memory_factory_cycle
from printer_v1.operator_cli.e2c_fixture_rehearsal import (
    RECOMMENDATION_FIXTURE_PASS,
    _OPTIONAL_TABLES,
    _REQUIRED_TABLES,
    _build_fixture_evidence_plan,
    _build_mutation_proof,
    _determine_rehearsal_recommendation,
    _snapshot_counts,
    build_e2c_fixture_rehearsal_payload,
)
from printer_v1.operator_cli.e2c_readiness import (
    HARD_LOCKS,
    RECOMMENDATION_BLOCKED,
    RECOMMENDATION_LIMITED_GO,
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
        self.db_path = pathlib.Path(self.tempdir.name) / "e2c_e_test.sqlite3"
        apply_migrations(self.db_path)

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
                ("e2c_e_test_job", "TRACK_FAST_FIRST_15M", status, "2026-06-27T12:00:00"),
            )
            if locked_at is not None:
                conn.execute(
                    "UPDATE printer_scheduler_jobs SET locked_at = ?"
                    " WHERE job_name = 'e2c_e_test_job'",
                    (locked_at,),
                )
            conn.commit()
        finally:
            conn.close()

    def _set_lock_owner(self, owner: str) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "UPDATE printer_scheduler_jobs SET lock_owner = ?"
                " WHERE job_name = 'e2c_e_test_job'",
                (owner,),
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

class LaneE2CEImportTests(unittest.TestCase):
    """Prove e2c_fixture_rehearsal module imports cleanly and constants are set."""

    def test_module_importable(self):
        import printer_v1.operator_cli.e2c_fixture_rehearsal as mod
        self.assertIsNotNone(mod)

    def test_recommendation_fixture_pass_value(self):
        self.assertEqual(RECOMMENDATION_FIXTURE_PASS, "FIXTURE_REHEARSAL_PASS")

    def test_cli_command_importable(self):
        self.assertTrue(callable(main_rehearse_bounded_15m_memory_factory_cycle))

    def test_required_tables_not_empty(self):
        self.assertGreater(len(_REQUIRED_TABLES), 0)

    def test_optional_tables_not_empty(self):
        self.assertGreater(len(_OPTIONAL_TABLES), 0)

    def test_scheduler_jobs_in_required_tables(self):
        self.assertIn("printer_scheduler_jobs", _REQUIRED_TABLES)

    def test_source_requests_in_required_tables(self):
        self.assertIn("printer_source_requests", _REQUIRED_TABLES)

    def test_paper_decisions_in_optional_tables(self):
        self.assertIn("printer_paper_decisions", _OPTIONAL_TABLES)

    def test_paper_positions_in_optional_tables(self):
        self.assertIn("printer_paper_positions", _OPTIONAL_TABLES)

    def test_no_http_libraries_imported(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(
                lib,
                sys.modules,
                f"Network library {lib!r} must not be imported by e2c_fixture_rehearsal",
            )

    def test_pyproject_entry_point_registered(self):
        pyproject = PROJECT_ROOT / "pyproject.toml"
        content = pyproject.read_text(encoding="utf-8")
        self.assertIn("printer-rehearse-bounded-15m-memory-factory-cycle", content)
        self.assertIn("main_rehearse_bounded_15m_memory_factory_cycle", content)


# ---------------------------------------------------------------------------
# Hard lock tests (from e2c_readiness, re-verified in fixture payload)
# ---------------------------------------------------------------------------

class LaneE2CEHardLockTests(unittest.TestCase):
    """Prove all 11 hard-lock flags are present and False."""

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

    def test_payload_hard_locks_all_false(self):
        with tempfile.TemporaryDirectory() as td:
            db = pathlib.Path(td) / "e2c_e_hl.sqlite3"
            apply_migrations(db)
            payload = build_e2c_fixture_rehearsal_payload(
                [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
                db,
                backup_confirmed=True,
            )
            for key, val in payload["hard_locks"].items():
                self.assertIs(val, False, f"payload hard_locks[{key!r}] must be False")

    def test_payload_hard_locks_count(self):
        with tempfile.TemporaryDirectory() as td:
            db = pathlib.Path(td) / "e2c_e_hlc.sqlite3"
            apply_migrations(db)
            payload = build_e2c_fixture_rehearsal_payload(
                [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
                db,
                backup_confirmed=True,
            )
            self.assertEqual(len(payload["hard_locks"]), 11)


# ---------------------------------------------------------------------------
# Fixture rehearsal pass cases
# ---------------------------------------------------------------------------

class LaneE2CERehearsalPassTests(_DbTestBase):
    """Prove FIXTURE_REHEARSAL_PASS for valid 1-token and 2-token inputs."""

    def test_single_token_track_fast_produces_fixture_pass(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_FIXTURE_PASS)

    def test_two_token_mixed_produces_fixture_pass(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [
                {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
                {"token_mint": _MINT_B, "lifecycle_lane": "TRACK_NORMAL"},
            ],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_FIXTURE_PASS)

    def test_single_token_track_normal_produces_fixture_pass(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_NORMAL"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_FIXTURE_PASS)

    def test_fixture_only_flag_true(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertTrue(payload["fixture_only"])

    def test_synthetic_evidence_only_flag_true(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertTrue(payload["synthetic_evidence_only"])

    def test_source_fetching_enabled_false_in_payload(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertFalse(payload["source_fetching_enabled"])

    def test_dry_run_flag_true(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertTrue(payload["dry_run"])

    def test_command_name_correct(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(
            payload["command"], "printer-rehearse-bounded-15m-memory-factory-cycle"
        )


# ---------------------------------------------------------------------------
# Token validation: reject cases
# ---------------------------------------------------------------------------

class LaneE2CETokenRejectTests(_DbTestBase):
    """Prove BLOCKED for invalid token inputs."""

    def test_zero_tokens_blocked(self):
        payload = build_e2c_fixture_rehearsal_payload([], self.db_path, backup_confirmed=True)
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_more_than_two_tokens_blocked(self):
        tokens = [
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
            {"token_mint": _MINT_B, "lifecycle_lane": "TRACK_NORMAL"},
            {"token_mint": "C" * 43, "lifecycle_lane": "TRACK_FAST"},
        ]
        payload = build_e2c_fixture_rehearsal_payload(tokens, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_duplicate_mints_blocked(self):
        tokens = [
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_NORMAL"},
        ]
        payload = build_e2c_fixture_rehearsal_payload(tokens, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_invalid_mint_format_blocked(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": "not-a-mint", "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_invalid_mint_contains_zero_char_blocked(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": "0" + "A" * 42, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_unsupported_lifecycle_lane_blocked(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_UNKNOWN"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_empty_lifecycle_lane_blocked(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": ""}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")


# ---------------------------------------------------------------------------
# DB preflight: blocking cases
# ---------------------------------------------------------------------------

class LaneE2CEDbPreflightTests(_DbTestBase):
    """Prove BLOCKED for DB preflight failures."""

    def test_missing_db_blocks(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            "/nonexistent/path/db.sqlite3",
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_none_db_path_blocks(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            None,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_backup_not_confirmed_blocks(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=False,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_running_job_blocks(self):
        self._insert_scheduler_job(status="RUNNING")
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_active_locked_at_blocks(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_active_lock_owner_blocks(self):
        self._insert_scheduler_job(status="PENDING")
        self._set_lock_owner("e2c_e_stale_owner")
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")


# ---------------------------------------------------------------------------
# Source budget: blocking case
# ---------------------------------------------------------------------------

class LaneE2CESourceBudgetTests(_DbTestBase):
    """Prove BLOCKED when source budget rate limit is exceeded."""

    def test_source_budget_rate_limit_exceeded_blocks(self):
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], "BLOCKED")

    def test_source_budget_below_limit_allows(self):
        for _ in range(_RATE_LIMIT - 1):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(payload["recommendation"], RECOMMENDATION_FIXTURE_PASS)


# ---------------------------------------------------------------------------
# Fixture evidence plan
# ---------------------------------------------------------------------------

class LaneE2CEFixtureEvidencePlanTests(_DbTestBase):
    """Prove fixture evidence plan structure is correct."""

    def _get_plan(self, lane: str = "TRACK_FAST", mint: str = _MINT_A) -> list:
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": mint, "lifecycle_lane": lane}],
            self.db_path,
            backup_confirmed=True,
        )
        return payload["fixture_evidence_plan"]

    def test_evidence_plan_has_one_entry_for_one_token(self):
        plan = self._get_plan()
        self.assertEqual(len(plan), 1)

    def test_evidence_plan_has_two_entries_for_two_tokens(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [
                {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
                {"token_mint": _MINT_B, "lifecycle_lane": "TRACK_NORMAL"},
            ],
            self.db_path,
            backup_confirmed=True,
        )
        self.assertEqual(len(payload["fixture_evidence_plan"]), 2)

    def test_evidence_plan_entry_fixture_only_true(self):
        plan = self._get_plan()
        self.assertTrue(plan[0]["fixture_only"])

    def test_evidence_plan_entry_synthetic_evidence_only_true(self):
        plan = self._get_plan()
        self.assertTrue(plan[0]["synthetic_evidence_only"])

    def test_evidence_plan_entry_source_fetching_disabled(self):
        plan = self._get_plan()
        self.assertFalse(plan[0]["source_fetching_enabled"])

    def test_evidence_plan_track_fast_job_kind(self):
        plan = self._get_plan(lane="TRACK_FAST")
        self.assertEqual(plan[0]["planned_job_kind"], "TRACK_FAST_FIRST_15M")

    def test_evidence_plan_track_normal_job_kind(self):
        plan = self._get_plan(lane="TRACK_NORMAL")
        self.assertEqual(plan[0]["planned_job_kind"], "TRACK_NORMAL_FIRST_15M")

    def test_evidence_plan_zero_snapshot_rows_created(self):
        plan = self._get_plan()
        self.assertEqual(plan[0]["snapshot_rows_created"], 0)

    def test_evidence_plan_zero_memory_rows_created(self):
        plan = self._get_plan()
        self.assertEqual(plan[0]["memory_rows_created"], 0)

    def test_evidence_plan_zero_context_rows_created(self):
        plan = self._get_plan()
        self.assertEqual(plan[0]["context_rows_created"], 0)

    def test_evidence_plan_zero_paper_decision_rows_created(self):
        plan = self._get_plan()
        self.assertEqual(plan[0]["paper_decision_rows_created"], 0)

    def test_evidence_placeholders_are_fixture_only(self):
        plan = self._get_plan()
        for placeholder in plan[0]["evidence_placeholders"]:
            self.assertTrue(
                placeholder["fixture_only"],
                f"placeholder {placeholder!r} must have fixture_only: true",
            )

    def test_evidence_placeholders_status_is_fixture_placeholder(self):
        plan = self._get_plan()
        for placeholder in plan[0]["evidence_placeholders"]:
            self.assertEqual(placeholder["status"], "fixture_placeholder")

    def test_evidence_placeholders_only_non_paid_sources(self):
        plan = self._get_plan()
        paid_sources = {
            name for name, defn in SOURCE_REGISTRY.items() if defn.requires_paid_plan
        }
        for placeholder in plan[0]["evidence_placeholders"]:
            self.assertNotIn(
                placeholder["source_name"],
                paid_sources,
                f"paid source {placeholder['source_name']!r} must not appear in fixture plan",
            )

    def test_evidence_plan_empty_for_blocked_payload(self):
        # When token validation fails, validated_tokens is empty -> no evidence plan entries.
        payload = build_e2c_fixture_rehearsal_payload([], self.db_path, backup_confirmed=True)
        self.assertEqual(payload["fixture_evidence_plan"], [])

    def test_build_fixture_evidence_plan_direct_track_fast(self):
        tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]
        plan = _build_fixture_evidence_plan(tokens)
        self.assertEqual(len(plan), 1)
        self.assertEqual(plan[0]["planned_job_kind"], "TRACK_FAST_FIRST_15M")
        self.assertTrue(plan[0]["fixture_only"])

    def test_build_fixture_evidence_plan_direct_track_normal(self):
        tokens = [{"token_mint": _MINT_B, "lifecycle_lane": "TRACK_NORMAL"}]
        plan = _build_fixture_evidence_plan(tokens)
        self.assertEqual(plan[0]["planned_job_kind"], "TRACK_NORMAL_FIRST_15M")


# ---------------------------------------------------------------------------
# Planned job shape
# ---------------------------------------------------------------------------

class LaneE2CEPlannedJobShapeTests(_DbTestBase):
    """Prove planned job kinds in e2c_readiness cycle_plan are correct."""

    def _get_job_kinds(self, tokens: list) -> list[str]:
        payload = build_e2c_fixture_rehearsal_payload(
            tokens, self.db_path, backup_confirmed=True
        )
        return [
            j["job_kind"]
            for j in payload["e2c_readiness"]["cycle_plan"]["planned_jobs"]
        ]

    def test_track_fast_produces_track_fast_first_15m(self):
        kinds = self._get_job_kinds([{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}])
        self.assertIn("TRACK_FAST_FIRST_15M", kinds)

    def test_track_normal_produces_track_normal_first_15m(self):
        kinds = self._get_job_kinds([{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_NORMAL"}])
        self.assertIn("TRACK_NORMAL_FIRST_15M", kinds)

    def test_cycle_plan_always_includes_memory_window_close(self):
        kinds = self._get_job_kinds([{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}])
        self.assertIn("MEMORY_WINDOW_CLOSE", kinds)

    def test_two_token_cycle_plan_includes_both_job_kinds(self):
        kinds = self._get_job_kinds([
            {"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"},
            {"token_mint": _MINT_B, "lifecycle_lane": "TRACK_NORMAL"},
        ])
        self.assertIn("TRACK_FAST_FIRST_15M", kinds)
        self.assertIn("TRACK_NORMAL_FIRST_15M", kinds)
        self.assertIn("MEMORY_WINDOW_CLOSE", kinds)


# ---------------------------------------------------------------------------
# Mutation proof
# ---------------------------------------------------------------------------

class LaneE2CEMutationProofTests(_DbTestBase):
    """Prove no DB mutation occurs during fixture rehearsal."""

    def _get_mutation_proof(self, tokens: list = None) -> dict:
        if tokens is None:
            tokens = [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}]
        payload = build_e2c_fixture_rehearsal_payload(
            tokens, self.db_path, backup_confirmed=True
        )
        return payload["mutation_proof"]

    def test_mutation_proof_all_counts_unchanged(self):
        proof = self._get_mutation_proof()
        self.assertTrue(proof["all_counts_unchanged"])

    def test_mutation_proof_no_changed_tables(self):
        proof = self._get_mutation_proof()
        self.assertEqual(proof["changed_tables"], [])

    def test_mutation_proof_scheduler_jobs_unchanged(self):
        proof = self._get_mutation_proof()
        before = proof["counts_before"].get("printer_scheduler_jobs")
        after = proof["counts_after"].get("printer_scheduler_jobs")
        self.assertEqual(before, after)

    def test_mutation_proof_source_requests_unchanged(self):
        proof = self._get_mutation_proof()
        before = proof["counts_before"].get("printer_source_requests")
        after = proof["counts_after"].get("printer_source_requests")
        self.assertEqual(before, after)

    def test_mutation_proof_source_responses_unchanged(self):
        proof = self._get_mutation_proof()
        before = proof["counts_before"].get("printer_source_responses")
        after = proof["counts_after"].get("printer_source_responses")
        self.assertEqual(before, after)

    def test_mutation_proof_source_failures_unchanged(self):
        proof = self._get_mutation_proof()
        before = proof["counts_before"].get("printer_source_failures")
        after = proof["counts_after"].get("printer_source_failures")
        self.assertEqual(before, after)

    def test_mutation_proof_paper_decisions_unchanged(self):
        proof = self._get_mutation_proof()
        before = proof["counts_before"].get("printer_paper_decisions")
        after = proof["counts_after"].get("printer_paper_decisions")
        if before != "table_missing":
            self.assertEqual(before, after)

    def test_mutation_proof_paper_positions_unchanged(self):
        proof = self._get_mutation_proof()
        before = proof["counts_before"].get("printer_paper_positions")
        after = proof["counts_after"].get("printer_paper_positions")
        if before != "table_missing":
            self.assertEqual(before, after)

    def test_optional_missing_tables_reported_as_table_missing(self):
        # printer_memories does not exist in the migrated schema -- must be table_missing.
        proof = self._get_mutation_proof()
        memories_before = proof["counts_before"].get("printer_memories")
        self.assertEqual(memories_before, "table_missing")

    def test_optional_missing_table_in_tables_missing_list(self):
        proof = self._get_mutation_proof()
        self.assertIn("printer_memories", proof["tables_missing"])

    def test_none_db_path_mutation_proof_no_tables_checked(self):
        payload = build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            None,
            backup_confirmed=True,
        )
        self.assertEqual(payload["mutation_proof"]["tables_checked"], {})

    def test_build_mutation_proof_direct_unchanged(self):
        before = {"printer_scheduler_jobs": 0, "printer_paper_decisions": "table_missing"}
        after = {"printer_scheduler_jobs": 0, "printer_paper_decisions": "table_missing"}
        proof = _build_mutation_proof(before, after)
        self.assertTrue(proof["all_counts_unchanged"])
        self.assertEqual(proof["changed_tables"], [])
        self.assertIn("printer_paper_decisions", proof["tables_missing"])

    def test_build_mutation_proof_direct_changed(self):
        before = {"printer_scheduler_jobs": 0}
        after = {"printer_scheduler_jobs": 1}
        proof = _build_mutation_proof(before, after)
        self.assertFalse(proof["all_counts_unchanged"])
        self.assertIn("printer_scheduler_jobs", proof["changed_tables"])

    def test_snapshot_counts_returns_dict(self):
        counts = _snapshot_counts(self.db_path)
        self.assertIsInstance(counts, dict)
        self.assertIn("printer_scheduler_jobs", counts)

    def test_snapshot_counts_none_path_returns_empty(self):
        counts = _snapshot_counts(None)
        self.assertEqual(counts, {})

    def test_snapshot_counts_scheduler_jobs_is_int(self):
        counts = _snapshot_counts(self.db_path)
        self.assertIsInstance(counts["printer_scheduler_jobs"], int)


# ---------------------------------------------------------------------------
# Recommendation logic: unit tests of _determine_rehearsal_recommendation
# ---------------------------------------------------------------------------

class LaneE2CERecommendationLogicTests(unittest.TestCase):
    """Prove _determine_rehearsal_recommendation pure function logic."""

    def _clean_e2c(self) -> dict:
        return {"recommendation": RECOMMENDATION_LIMITED_GO, "recommendation_reasons": []}

    def _blocked_e2c(self, msg: str = "test block") -> dict:
        return {"recommendation": "BLOCKED", "recommendation_reasons": [msg]}

    def _clean_proof(self) -> dict:
        return {"all_counts_unchanged": True, "changed_tables": []}

    def _dirty_proof(self) -> dict:
        return {"all_counts_unchanged": False, "changed_tables": ["printer_scheduler_jobs"]}

    def test_fixture_pass_when_both_clean(self):
        rec, reasons = _determine_rehearsal_recommendation(self._clean_e2c(), self._clean_proof())
        self.assertEqual(rec, RECOMMENDATION_FIXTURE_PASS)

    def test_blocked_when_e2c_blocked(self):
        rec, reasons = _determine_rehearsal_recommendation(
            self._blocked_e2c(), self._clean_proof()
        )
        self.assertEqual(rec, "BLOCKED")

    def test_blocked_when_mutation_proof_failed(self):
        rec, reasons = _determine_rehearsal_recommendation(
            self._clean_e2c(), self._dirty_proof()
        )
        self.assertEqual(rec, "BLOCKED")
        self.assertTrue(any("mutation proof failed" in r for r in reasons))

    def test_blocked_when_both_e2c_blocked_and_mutation_dirty(self):
        rec, reasons = _determine_rehearsal_recommendation(
            self._blocked_e2c(), self._dirty_proof()
        )
        self.assertEqual(rec, "BLOCKED")

    def test_fixture_pass_reasons_are_informative(self):
        _, reasons = _determine_rehearsal_recommendation(self._clean_e2c(), self._clean_proof())
        self.assertGreater(len(reasons), 3)
        self.assertTrue(any("fixture rehearsal complete" in r for r in reasons))


# ---------------------------------------------------------------------------
# Payload structure and JSON-serializability
# ---------------------------------------------------------------------------

class LaneE2CEPayloadStructureTests(_DbTestBase):
    """Prove payload fields and JSON-serializability."""

    def _pass_payload(self) -> dict:
        return build_e2c_fixture_rehearsal_payload(
            [{"token_mint": _MINT_A, "lifecycle_lane": "TRACK_FAST"}],
            self.db_path,
            backup_confirmed=True,
        )

    def test_payload_is_json_serializable_pass(self):
        payload = self._pass_payload()
        serialized = json.dumps(payload)
        self.assertIsInstance(serialized, str)
        self.assertGreater(len(serialized), 50)

    def test_payload_is_json_serializable_blocked(self):
        payload = build_e2c_fixture_rehearsal_payload([], self.db_path, backup_confirmed=True)
        serialized = json.dumps(payload)
        self.assertIsInstance(serialized, str)

    def test_payload_has_command_key(self):
        payload = self._pass_payload()
        self.assertIn("command", payload)

    def test_payload_has_dry_run_key(self):
        payload = self._pass_payload()
        self.assertIn("dry_run", payload)

    def test_payload_has_fixture_only_key(self):
        payload = self._pass_payload()
        self.assertIn("fixture_only", payload)

    def test_payload_has_synthetic_evidence_only_key(self):
        payload = self._pass_payload()
        self.assertIn("synthetic_evidence_only", payload)

    def test_payload_has_source_fetching_enabled_key(self):
        payload = self._pass_payload()
        self.assertIn("source_fetching_enabled", payload)

    def test_payload_has_e2c_readiness_key(self):
        payload = self._pass_payload()
        self.assertIn("e2c_readiness", payload)

    def test_payload_has_fixture_evidence_plan_key(self):
        payload = self._pass_payload()
        self.assertIn("fixture_evidence_plan", payload)

    def test_payload_has_mutation_proof_key(self):
        payload = self._pass_payload()
        self.assertIn("mutation_proof", payload)

    def test_payload_has_hard_locks_key(self):
        payload = self._pass_payload()
        self.assertIn("hard_locks", payload)

    def test_payload_has_recommendation_key(self):
        payload = self._pass_payload()
        self.assertIn("recommendation", payload)

    def test_payload_has_recommendation_reasons_key(self):
        payload = self._pass_payload()
        self.assertIn("recommendation_reasons", payload)

    def test_e2c_readiness_nested_has_token_list_validation(self):
        payload = self._pass_payload()
        self.assertIn("token_list_validation", payload["e2c_readiness"])

    def test_e2c_readiness_nested_has_db_preflight(self):
        payload = self._pass_payload()
        self.assertIn("db_preflight", payload["e2c_readiness"])

    def test_e2c_readiness_nested_has_source_budget(self):
        payload = self._pass_payload()
        self.assertIn("source_budget", payload["e2c_readiness"])

    def test_e2c_readiness_nested_has_cycle_plan(self):
        payload = self._pass_payload()
        self.assertIn("cycle_plan", payload["e2c_readiness"])

    def test_e2c_readiness_nested_hard_locks_all_false(self):
        payload = self._pass_payload()
        for key, val in payload["e2c_readiness"]["hard_locks"].items():
            self.assertIs(val, False, f"e2c_readiness.hard_locks[{key!r}] must be False")

    def test_no_paper_decisions_in_module_imports(self):
        import printer_v1.operator_cli.e2c_fixture_rehearsal as mod
        src = pathlib.Path(mod.__file__).read_text(encoding="utf-8")
        forbidden = ["paper_decision", "BUY", "SELL", "HOLD", "positions", "pnl"]
        for term in forbidden:
            self.assertNotIn(
                f'"{term}"',
                src,
                f"Forbidden term {term!r} found as string literal in e2c_fixture_rehearsal.py",
            )


# ---------------------------------------------------------------------------
# CLI command tests
# ---------------------------------------------------------------------------

class LaneE2CECliTests(_DbTestBase):
    """Prove CLI command outputs valid JSON."""

    def test_cli_returns_0_for_valid_input(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_rehearse_bounded_15m_memory_factory_cycle([
                "--token", f"{_MINT_A}:TRACK_FAST",
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_rehearse_bounded_15m_memory_factory_cycle([
                "--token", f"{_MINT_A}:TRACK_FAST",
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        output = captured.getvalue()
        parsed = json.loads(output)
        self.assertIn("recommendation", parsed)

    def test_cli_fixture_pass_recommendation_in_json(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_rehearse_bounded_15m_memory_factory_cycle([
                "--token", f"{_MINT_A}:TRACK_FAST",
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed["recommendation"], RECOMMENDATION_FIXTURE_PASS)

    def test_cli_blocked_without_backup_confirmed(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_rehearse_bounded_15m_memory_factory_cycle([
                "--token", f"{_MINT_A}:TRACK_FAST",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed["recommendation"], "BLOCKED")

    def test_cli_two_tokens_produces_fixture_pass(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_rehearse_bounded_15m_memory_factory_cycle([
                "--token", f"{_MINT_A}:TRACK_FAST",
                "--token", f"{_MINT_B}:TRACK_NORMAL",
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed["recommendation"], RECOMMENDATION_FIXTURE_PASS)

    def test_cli_no_source_fetching_in_output(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_rehearse_bounded_15m_memory_factory_cycle([
                "--token", f"{_MINT_A}:TRACK_FAST",
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        parsed = json.loads(captured.getvalue())
        self.assertFalse(parsed["source_fetching_enabled"])


if __name__ == "__main__":
    unittest.main()
