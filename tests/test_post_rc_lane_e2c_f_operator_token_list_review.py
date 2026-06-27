"""
Post-Lane 10 Lane E2C-F -- Operator Token List Review and E2C Closeout Package

Tests prove:
- e2c_operator_review module imports cleanly and exports are present
- FINAL_RECOMMENDATION_READY, E2C_STATUS_READY, E2C_STATUS_BLOCKED constants correct
- pyproject.toml entry point registered
- valid 1-token READY_FOR_OPERATOR_DECISION
- valid 2-token mixed READY_FOR_OPERATOR_DECISION
- missing/invalid token file produces BLOCKED
- missing tokens[] key produces BLOCKED
- zero tokens produces BLOCKED
- more than 2 tokens produces BLOCKED
- missing required fields produces BLOCKED
- approved_by_operator false produces BLOCKED
- approved_by_operator non-bool produces BLOCKED
- blank operator_note produces BLOCKED
- placeholder mint 43 A chars produces BLOCKED
- placeholder mint 44 B chars produces BLOCKED
- placeholder substring in mint produces BLOCKED
- duplicate mints produce BLOCKED
- invalid mint format produces BLOCKED
- invalid lifecycle_lane produces BLOCKED
- backup not confirmed produces BLOCKED
- DB missing produces BLOCKED
- RUNNING scheduler job produces BLOCKED
- locked_at active lock produces BLOCKED
- lock_owner active lock produces BLOCKED
- source budget rate-limit-exceeded produces BLOCKED
- E2C-C readiness payload included in output
- E2C-E fixture rehearsal payload included in output
- no persistent DB mutation (row counts unchanged)
- all 11 hard-lock flags false
- payload is JSON-serializable
- CLI outputs valid JSON
- BLOCKED result still returns 0 from CLI
- no source-fetching libraries imported
- closeout doc exists with required statements
- e2c_status correct for READY and BLOCKED cases
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
from printer_v1.operator_cli.commands import main_review_bounded_15m_token_list_rehearsal
from printer_v1.operator_cli.e2c_operator_review import (
    E2C_STATUS_BLOCKED,
    E2C_STATUS_READY,
    FINAL_RECOMMENDATION_READY,
    _PLACEHOLDER_MINTS,
    _PLACEHOLDER_SUBSTRINGS,
    _is_placeholder_mint,
    _review_token_file,
    build_e2c_operator_review_payload,
)
from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS
from printer_v1.sources.contracts import NormalizedSourceResult, build_governed_source_request
from printer_v1.sources.recording import record_source_request, record_source_response
from printer_v1.sources.registry import SOURCE_REGISTRY


# Structurally valid Solana base58 test mints -- NOT placeholders.
# "C" and "D" are base58 chars; these do not match any placeholder pattern.
_MINT_1 = "C" * 43   # 43 chars, all 'C'
_MINT_2 = "D" * 44   # 44 chars, all 'D'

# Placeholder mints that must be rejected.
_PLACEHOLDER_43A = "A" * 43
_PLACEHOLDER_44B = "B" * 44

_RATE_LIMIT_SOURCE = "alternative_me"
_RATE_LIMIT_KIND = "fear_greed_context"
_RATE_LIMIT = SOURCE_REGISTRY[_RATE_LIMIT_SOURCE].default_rate_limit_per_minute

_VALID_NOTE = "Operator-approved for E2C-F test. Identified via manual review 2026-06-27."


class _DbTestBase(unittest.TestCase):
    """Temp SQLite with migrations applied plus temp dir for token files."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2c_f_test.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_token_file(self, tokens: list, extra: dict | None = None) -> pathlib.Path:
        data: dict = {"tokens": tokens}
        if extra:
            data.update(extra)
        path = pathlib.Path(self.tempdir.name) / "token_list.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def _valid_entry(self, mint: str, lane: str = "TRACK_FAST") -> dict:
        return {
            "token_mint": mint,
            "lifecycle_lane": lane,
            "operator_note": _VALID_NOTE,
            "approved_by_operator": True,
        }

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
                ("e2c_f_test_job", "TRACK_FAST_FIRST_15M", status, "2026-06-27T12:00:00"),
            )
            if locked_at is not None:
                conn.execute(
                    "UPDATE printer_scheduler_jobs SET locked_at = ?"
                    " WHERE job_name = 'e2c_f_test_job'",
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
                " WHERE job_name = 'e2c_f_test_job'",
                (owner,),
            )
            conn.commit()
        finally:
            conn.close()

    def _record_success_attempt(self, source_name: str, request_kind: str) -> None:
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

class LaneE2CFImportTests(unittest.TestCase):
    """Prove module imports cleanly and constants are correct."""

    def test_module_importable(self):
        import printer_v1.operator_cli.e2c_operator_review as mod
        self.assertIsNotNone(mod)

    def test_final_recommendation_ready_value(self):
        self.assertEqual(FINAL_RECOMMENDATION_READY, "READY_FOR_OPERATOR_DECISION")

    def test_e2c_status_ready_value(self):
        self.assertEqual(E2C_STATUS_READY, "E2C_READY_TO_CLOSE_AFTER_COMMIT_TAG")

    def test_e2c_status_blocked_value(self):
        self.assertEqual(E2C_STATUS_BLOCKED, "E2C_REVIEW_BLOCKED")

    def test_placeholder_mints_contains_43_a(self):
        self.assertIn("A" * 43, _PLACEHOLDER_MINTS)

    def test_placeholder_mints_contains_44_b(self):
        self.assertIn("B" * 44, _PLACEHOLDER_MINTS)

    def test_placeholder_substrings_contains_replace(self):
        self.assertIn("REPLACE_WITH_REAL_MINT", _PLACEHOLDER_SUBSTRINGS)

    def test_placeholder_substrings_contains_placeholder(self):
        self.assertIn("PLACEHOLDER", _PLACEHOLDER_SUBSTRINGS)

    def test_placeholder_substrings_contains_token_mint(self):
        self.assertIn("TOKEN_MINT", _PLACEHOLDER_SUBSTRINGS)

    def test_cli_command_importable(self):
        self.assertTrue(callable(main_review_bounded_15m_token_list_rehearsal))

    def test_no_http_libraries_imported(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(lib, sys.modules,
                f"Network library {lib!r} must not be imported by e2c_operator_review")

    def test_pyproject_entry_point_registered(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-review-bounded-15m-token-list-rehearsal", content)
        self.assertIn("main_review_bounded_15m_token_list_rehearsal", content)


# ---------------------------------------------------------------------------
# Placeholder mint detection
# ---------------------------------------------------------------------------

class LaneE2CFPlaceholderTests(unittest.TestCase):
    """Prove _is_placeholder_mint correctly identifies placeholders."""

    def test_43_a_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("A" * 43))

    def test_44_b_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("B" * 44))

    def test_replace_substring_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("REPLACE_WITH_REAL_MINT"))

    def test_placeholder_substring_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("PLACEHOLDER_SOMETHING"))

    def test_token_mint_substring_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("TOKEN_MINT_HERE"))

    def test_example_substring_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("example_address"))

    def test_demo_substring_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("demo_token"))

    def test_test_substring_is_placeholder(self):
        self.assertTrue(_is_placeholder_mint("test_mint_value"))

    def test_valid_mint_c43_is_not_placeholder(self):
        self.assertFalse(_is_placeholder_mint(_MINT_1))

    def test_valid_mint_d44_is_not_placeholder(self):
        self.assertFalse(_is_placeholder_mint(_MINT_2))


# ---------------------------------------------------------------------------
# Token file review: pass cases
# ---------------------------------------------------------------------------

class LaneE2CFTokenFilePassTests(unittest.TestCase):
    """Prove _review_token_file accepts valid token entries."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def _write(self, tokens: list) -> pathlib.Path:
        p = pathlib.Path(self.tempdir.name) / "tokens.json"
        p.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return p

    def _entry(self, mint: str, lane: str = "TRACK_FAST") -> dict:
        return {"token_mint": mint, "lifecycle_lane": lane,
                "operator_note": _VALID_NOTE, "approved_by_operator": True}

    def test_valid_single_token_track_fast(self):
        result = _review_token_file(self._write([self._entry(_MINT_1)]))
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["token_count"], 1)
        self.assertEqual(len(result["clean_token_entries"]), 1)

    def test_valid_two_token_mixed(self):
        result = _review_token_file(self._write([
            self._entry(_MINT_1, "TRACK_FAST"),
            self._entry(_MINT_2, "TRACK_NORMAL"),
        ]))
        self.assertTrue(result["valid"])
        self.assertEqual(result["token_count"], 2)
        self.assertEqual(len(result["clean_token_entries"]), 2)

    def test_valid_single_token_track_normal(self):
        result = _review_token_file(self._write([self._entry(_MINT_1, "TRACK_NORMAL")]))
        self.assertTrue(result["valid"])

    def test_clean_entries_contain_only_mint_and_lane(self):
        result = _review_token_file(self._write([self._entry(_MINT_1)]))
        entry = result["clean_token_entries"][0]
        self.assertEqual(set(entry.keys()), {"token_mint", "lifecycle_lane"})

    def test_file_readable_true_for_valid_file(self):
        result = _review_token_file(self._write([self._entry(_MINT_1)]))
        self.assertTrue(result["file_readable"])


# ---------------------------------------------------------------------------
# Token file review: reject cases
# ---------------------------------------------------------------------------

class LaneE2CFTokenFileRejectTests(unittest.TestCase):
    """Prove _review_token_file rejects invalid inputs."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.tempdir.cleanup()

    def _write(self, data: object) -> pathlib.Path:
        p = pathlib.Path(self.tempdir.name) / "tokens.json"
        p.write_text(json.dumps(data), encoding="utf-8")
        return p

    def _entry(self, mint: str, lane: str = "TRACK_FAST", **kw) -> dict:
        base = {"token_mint": mint, "lifecycle_lane": lane,
                "operator_note": _VALID_NOTE, "approved_by_operator": True}
        base.update(kw)
        return base

    def test_none_path_produces_not_valid(self):
        result = _review_token_file(None)
        self.assertFalse(result["valid"])
        self.assertIn("no token_file_path provided", result["errors"][0])

    def test_missing_file_produces_not_valid(self):
        result = _review_token_file("/nonexistent/path/tokens.json")
        self.assertFalse(result["valid"])
        self.assertFalse(result["file_readable"])

    def test_invalid_json_produces_not_valid(self):
        p = pathlib.Path(self.tempdir.name) / "bad.json"
        p.write_text("not valid json {{{", encoding="utf-8")
        result = _review_token_file(p)
        self.assertFalse(result["valid"])
        self.assertFalse(result["file_readable"])

    def test_missing_tokens_key_produces_not_valid(self):
        result = _review_token_file(self._write({"other_key": []}))
        self.assertFalse(result["valid"])
        self.assertTrue(any("tokens" in e for e in result["errors"]))

    def test_zero_tokens_produces_not_valid(self):
        result = _review_token_file(self._write({"tokens": []}))
        self.assertFalse(result["valid"])
        self.assertTrue(any("at least 1" in e for e in result["errors"]))

    def test_three_tokens_produces_not_valid(self):
        tokens = [self._entry(_MINT_1), self._entry(_MINT_2),
                  self._entry("C" * 44)]
        result = _review_token_file(self._write({"tokens": tokens}))
        self.assertFalse(result["valid"])
        self.assertTrue(any("at most 2" in e for e in result["errors"]))

    def test_missing_token_mint_field_produces_not_valid(self):
        entry = {"lifecycle_lane": "TRACK_FAST", "operator_note": _VALID_NOTE,
                 "approved_by_operator": True}
        result = _review_token_file(self._write({"tokens": [entry]}))
        self.assertFalse(result["valid"])
        self.assertTrue(any("token_mint" in e for e in result["errors"]))

    def test_missing_lifecycle_lane_field_produces_not_valid(self):
        entry = {"token_mint": _MINT_1, "operator_note": _VALID_NOTE,
                 "approved_by_operator": True}
        result = _review_token_file(self._write({"tokens": [entry]}))
        self.assertFalse(result["valid"])
        self.assertTrue(any("lifecycle_lane" in e for e in result["errors"]))

    def test_missing_operator_note_field_produces_not_valid(self):
        entry = {"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
                 "approved_by_operator": True}
        result = _review_token_file(self._write({"tokens": [entry]}))
        self.assertFalse(result["valid"])

    def test_missing_approved_by_operator_field_produces_not_valid(self):
        entry = {"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
                 "operator_note": _VALID_NOTE}
        result = _review_token_file(self._write({"tokens": [entry]}))
        self.assertFalse(result["valid"])

    def test_approved_by_operator_false_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_MINT_1, approved_by_operator=False)]}
        ))
        self.assertFalse(result["valid"])
        self.assertTrue(any("approved_by_operator" in e for e in result["errors"]))

    def test_approved_by_operator_string_true_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_MINT_1, approved_by_operator="true")]}
        ))
        self.assertFalse(result["valid"])
        self.assertTrue(any("approved_by_operator" in e for e in result["errors"]))

    def test_approved_by_operator_int_1_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_MINT_1, approved_by_operator=1)]}
        ))
        self.assertFalse(result["valid"])

    def test_blank_operator_note_empty_string_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_MINT_1, operator_note="")]}
        ))
        self.assertFalse(result["valid"])
        self.assertTrue(any("operator_note" in e for e in result["errors"]))

    def test_whitespace_only_operator_note_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_MINT_1, operator_note="   ")]}
        ))
        self.assertFalse(result["valid"])

    def test_placeholder_43_a_mint_blocked(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_PLACEHOLDER_43A)]}
        ))
        self.assertFalse(result["valid"])
        self.assertTrue(any("placeholder" in e for e in result["errors"]))

    def test_placeholder_44_b_mint_blocked(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_PLACEHOLDER_44B)]}
        ))
        self.assertFalse(result["valid"])
        self.assertTrue(any("placeholder" in e for e in result["errors"]))

    def test_invalid_mint_format_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry("not-a-valid-mint")]}
        ))
        self.assertFalse(result["valid"])

    def test_mint_with_zero_char_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry("0" + "C" * 42)]}
        ))
        self.assertFalse(result["valid"])

    def test_duplicate_mints_produce_not_valid(self):
        result = _review_token_file(self._write({"tokens": [
            self._entry(_MINT_1, "TRACK_FAST"),
            self._entry(_MINT_1, "TRACK_NORMAL"),
        ]}))
        self.assertFalse(result["valid"])
        self.assertTrue(any("duplicate" in e for e in result["errors"]))

    def test_invalid_lifecycle_lane_produces_not_valid(self):
        result = _review_token_file(self._write(
            {"tokens": [self._entry(_MINT_1, "TRACK_UNKNOWN")]}
        ))
        self.assertFalse(result["valid"])
        self.assertTrue(any("lifecycle_lane" in e for e in result["errors"]))

    def test_clean_entries_empty_when_invalid(self):
        result = _review_token_file(self._write({"tokens": []}))
        self.assertEqual(result["clean_token_entries"], [])


# ---------------------------------------------------------------------------
# Full payload: READY_FOR_OPERATOR_DECISION cases
# ---------------------------------------------------------------------------

class LaneE2CFReadyPayloadTests(_DbTestBase):
    """Prove READY_FOR_OPERATOR_DECISION for valid inputs."""

    def _ready_payload_1(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1, "TRACK_FAST")])
        return build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)

    def _ready_payload_2(self) -> dict:
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        return build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)

    def test_single_token_produces_ready(self):
        payload = self._ready_payload_1()
        self.assertEqual(payload["final_recommendation"], FINAL_RECOMMENDATION_READY)

    def test_two_token_mixed_produces_ready(self):
        payload = self._ready_payload_2()
        self.assertEqual(payload["final_recommendation"], FINAL_RECOMMENDATION_READY)

    def test_e2c_status_ready_when_ready(self):
        payload = self._ready_payload_1()
        self.assertEqual(payload["e2c_status"], E2C_STATUS_READY)

    def test_dry_run_true(self):
        self.assertTrue(self._ready_payload_1()["dry_run"])

    def test_operator_review_only_true(self):
        self.assertTrue(self._ready_payload_1()["operator_review_only"])

    def test_e2c_closeout_candidate_true(self):
        self.assertTrue(self._ready_payload_1()["e2c_closeout_candidate"])

    def test_command_name_correct(self):
        self.assertEqual(
            self._ready_payload_1()["command"],
            "printer-review-bounded-15m-token-list-rehearsal",
        )


# ---------------------------------------------------------------------------
# Full payload: BLOCKED cases from token file
# ---------------------------------------------------------------------------

class LaneE2CFBlockedTokenFileTests(_DbTestBase):
    """Prove BLOCKED when token file is invalid."""

    def test_missing_file_path_blocked(self):
        payload = build_e2c_operator_review_payload(
            None, self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")
        self.assertEqual(payload["e2c_status"], E2C_STATUS_BLOCKED)

    def test_nonexistent_file_blocked(self):
        payload = build_e2c_operator_review_payload(
            "/no/such/file.json", self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_zero_tokens_blocked(self):
        tf = self._write_token_file([])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_three_tokens_blocked(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
            self._valid_entry("C" * 44, "TRACK_FAST"),
        ])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_placeholder_43a_blocked(self):
        tf = self._write_token_file([self._valid_entry(_PLACEHOLDER_43A)])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_placeholder_44b_blocked(self):
        tf = self._write_token_file([self._valid_entry(_PLACEHOLDER_44B)])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_approved_false_blocked(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
            "operator_note": _VALID_NOTE, "approved_by_operator": False,
        }])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_approved_non_bool_blocked(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
            "operator_note": _VALID_NOTE, "approved_by_operator": "true",
        }])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_blank_note_blocked(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
            "operator_note": "", "approved_by_operator": True,
        }])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_bad_mint_blocked(self):
        tf = self._write_token_file([self._valid_entry("not-a-mint")])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_bad_lane_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1, "TRACK_UNKNOWN")])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_duplicate_mints_blocked(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_1, "TRACK_NORMAL"),
        ])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")


# ---------------------------------------------------------------------------
# Full payload: BLOCKED cases from DB preflight
# ---------------------------------------------------------------------------

class LaneE2CFBlockedDbTests(_DbTestBase):
    """Prove BLOCKED when DB preflight fails."""

    def _tf(self) -> pathlib.Path:
        return self._write_token_file([self._valid_entry(_MINT_1, "TRACK_FAST")])

    def test_backup_not_confirmed_blocked(self):
        payload = build_e2c_operator_review_payload(
            self._tf(), self.db_path, backup_confirmed=False
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_missing_db_path_blocked(self):
        payload = build_e2c_operator_review_payload(
            self._tf(), "/nonexistent/db.sqlite3", backup_confirmed=True
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_none_db_path_blocked(self):
        payload = build_e2c_operator_review_payload(
            self._tf(), None, backup_confirmed=True
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_running_job_blocked(self):
        self._insert_scheduler_job(status="RUNNING")
        payload = build_e2c_operator_review_payload(
            self._tf(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_locked_at_blocked(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        payload = build_e2c_operator_review_payload(
            self._tf(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_lock_owner_blocked(self):
        self._insert_scheduler_job(status="PENDING")
        self._set_lock_owner("e2c_f_stale_owner")
        payload = build_e2c_operator_review_payload(
            self._tf(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_recommendation"], "BLOCKED")


# ---------------------------------------------------------------------------
# Full payload: BLOCKED from source budget
# ---------------------------------------------------------------------------

class LaneE2CFSourceBudgetTests(_DbTestBase):
    """Prove BLOCKED when source budget is rate-limited."""

    def test_rate_limit_exceeded_blocked(self):
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        tf = self._write_token_file([self._valid_entry(_MINT_1, "TRACK_FAST")])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_below_rate_limit_allows_ready(self):
        for _ in range(_RATE_LIMIT - 1):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        tf = self._write_token_file([self._valid_entry(_MINT_1, "TRACK_FAST")])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_recommendation"], FINAL_RECOMMENDATION_READY)


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------

class LaneE2CFPayloadStructureTests(_DbTestBase):
    """Prove payload contains all required keys and correct structure."""

    def _ready(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        return build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)

    def _blocked(self) -> dict:
        return build_e2c_operator_review_payload(None, self.db_path, backup_confirmed=True)

    def test_has_command_key(self):
        self.assertIn("command", self._ready())

    def test_has_dry_run_key(self):
        self.assertIn("dry_run", self._ready())

    def test_has_operator_review_only_key(self):
        self.assertIn("operator_review_only", self._ready())

    def test_has_e2c_closeout_candidate_key(self):
        self.assertIn("e2c_closeout_candidate", self._ready())

    def test_has_token_file_review_key(self):
        self.assertIn("token_file_review", self._ready())

    def test_has_e2c_readiness_review_key(self):
        self.assertIn("e2c_readiness_review", self._ready())

    def test_has_fixture_rehearsal_review_key(self):
        self.assertIn("fixture_rehearsal_review", self._ready())

    def test_has_hard_locks_key(self):
        self.assertIn("hard_locks", self._ready())

    def test_has_final_recommendation_key(self):
        self.assertIn("final_recommendation", self._ready())

    def test_has_final_recommendation_reasons_key(self):
        self.assertIn("final_recommendation_reasons", self._ready())

    def test_has_e2c_status_key(self):
        self.assertIn("e2c_status", self._ready())

    def test_e2c_readiness_review_has_recommendation(self):
        payload = self._ready()
        self.assertIn("recommendation", payload["e2c_readiness_review"])

    def test_e2c_readiness_review_recommendation_is_limited_go(self):
        payload = self._ready()
        self.assertEqual(
            payload["e2c_readiness_review"]["recommendation"],
            "LIMITED_GO_FOR_OPERATOR_REVIEW",
        )

    def test_fixture_rehearsal_review_has_recommendation(self):
        payload = self._ready()
        self.assertIn("recommendation", payload["fixture_rehearsal_review"])

    def test_fixture_rehearsal_review_recommendation_is_fixture_pass(self):
        payload = self._ready()
        self.assertEqual(
            payload["fixture_rehearsal_review"]["recommendation"],
            "FIXTURE_REHEARSAL_PASS",
        )

    def test_fixture_rehearsal_review_has_mutation_proof(self):
        payload = self._ready()
        self.assertIn("mutation_proof", payload["fixture_rehearsal_review"])

    def test_token_file_review_valid_true_for_ready(self):
        payload = self._ready()
        self.assertTrue(payload["token_file_review"]["valid"])

    def test_token_file_review_valid_false_for_blocked(self):
        payload = self._blocked()
        self.assertFalse(payload["token_file_review"]["valid"])

    def test_payload_json_serializable_ready(self):
        s = json.dumps(self._ready())
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 100)

    def test_payload_json_serializable_blocked(self):
        s = json.dumps(self._blocked())
        self.assertIsInstance(s, str)


# ---------------------------------------------------------------------------
# Hard lock tests
# ---------------------------------------------------------------------------

class LaneE2CFHardLockTests(_DbTestBase):
    """Prove all 11 hard-lock flags are False in payload."""

    def test_all_hard_locks_false_in_ready_payload(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False")

    def test_hard_locks_count_is_11(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(len(payload["hard_locks"]), 11)

    def test_all_hard_locks_false_in_blocked_payload(self):
        payload = build_e2c_operator_review_payload(None, self.db_path, backup_confirmed=True)
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False even when BLOCKED")

    def test_source_fetching_enabled_false(self):
        self.assertIs(HARD_LOCKS["source_fetching_enabled"], False)

    def test_buy_enabled_false(self):
        self.assertIs(HARD_LOCKS["buy_enabled"], False)

    def test_sell_enabled_false(self):
        self.assertIs(HARD_LOCKS["sell_enabled"], False)

    def test_hold_enabled_false(self):
        self.assertIs(HARD_LOCKS["hold_enabled"], False)

    def test_positions_enabled_false(self):
        self.assertIs(HARD_LOCKS["positions_enabled"], False)

    def test_pnl_enabled_false(self):
        self.assertIs(HARD_LOCKS["pnl_enabled"], False)


# ---------------------------------------------------------------------------
# Mutation proof
# ---------------------------------------------------------------------------

class LaneE2CFMutationProofTests(_DbTestBase):
    """Prove no persistent DB mutation during operator review."""

    def test_row_counts_unchanged_for_ready_payload(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_scheduler_jobs")
        build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_scheduler_jobs")
        self.assertEqual(before, after)

    def test_source_requests_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_requests")
        build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_source_requests")
        self.assertEqual(before, after)

    def test_source_responses_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_responses")
        build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_source_responses")
        self.assertEqual(before, after)

    def test_mutation_proof_in_fixture_rehearsal_all_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2c_operator_review_payload(tf, self.db_path, backup_confirmed=True)
        proof = payload["fixture_rehearsal_review"]["mutation_proof"]
        self.assertTrue(proof["all_counts_unchanged"])
        self.assertEqual(proof["changed_tables"], [])


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2CFCliTests(_DbTestBase):
    """Prove CLI command outputs valid JSON and returns 0."""

    def _run_cli(self, extra_args: list[str] | None = None) -> tuple[int, dict]:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        args = [
            "--token-list-path", str(tf),
            "--backup-confirmed",
            "--db-path", str(self.db_path),
            "--format", "json",
        ]
        if extra_args:
            args.extend(extra_args)
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_review_bounded_15m_token_list_rehearsal(args)
        return rc, json.loads(captured.getvalue())

    def test_cli_returns_0_for_ready(self):
        rc, _ = self._run_cli()
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json_for_ready(self):
        _, payload = self._run_cli()
        self.assertIn("final_recommendation", payload)

    def test_cli_ready_recommendation(self):
        _, payload = self._run_cli()
        self.assertEqual(payload["final_recommendation"], FINAL_RECOMMENDATION_READY)

    def test_cli_returns_0_for_blocked(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_review_bounded_15m_token_list_rehearsal([
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_cli_blocked_without_backup_confirmed_returns_0(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_review_bounded_15m_token_list_rehearsal([
                "--token-list-path", str(tf),
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["final_recommendation"], "BLOCKED")

    def test_cli_two_tokens_ready(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_review_bounded_15m_token_list_rehearsal([
                "--token-list-path", str(tf),
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["final_recommendation"], FINAL_RECOMMENDATION_READY)

    def test_cli_output_has_e2c_status(self):
        _, payload = self._run_cli()
        self.assertIn("e2c_status", payload)
        self.assertEqual(payload["e2c_status"], E2C_STATUS_READY)


# ---------------------------------------------------------------------------
# Closeout doc required statements
# ---------------------------------------------------------------------------

class LaneE2CFCloseoutDocTests(unittest.TestCase):
    """Prove closeout doc exists with required statements."""

    def _doc(self) -> str:
        path = PROJECT_ROOT / "docs" / "printer-v1-lane-e2c-final-closeout.md"
        self.assertTrue(path.exists(), f"closeout doc not found: {path}")
        return path.read_text(encoding="utf-8")

    def test_closeout_doc_exists(self):
        path = PROJECT_ROOT / "docs" / "printer-v1-lane-e2c-final-closeout.md"
        self.assertTrue(path.exists())

    def test_doc_mentions_e2c_series_summary(self):
        doc = self._doc()
        self.assertIn("E2C", doc)

    def test_doc_states_closeout_does_not_authorize_real_execution(self):
        doc = self._doc()
        self.assertTrue(
            "does NOT authorize" in doc or "does not authorize" in doc.lower(),
            "closeout doc must state it does NOT authorize real execution",
        )

    def test_doc_states_next_lane_outside_e2c(self):
        doc = self._doc()
        self.assertTrue(
            "next lane" in doc.lower() or "outside" in doc.lower(),
            "closeout doc must describe next lane boundary outside E2C",
        )

    def test_doc_mentions_all_v1_restrictions_remain_active(self):
        doc = self._doc()
        self.assertTrue(
            "restrictions" in doc.lower() or "remain" in doc.lower(),
            "closeout doc must state V1 restrictions remain active",
        )

    def test_doc_mentions_lane_e2c_a_through_f(self):
        doc = self._doc()
        for lane in ("E2C-A", "E2C-B", "E2C-C", "E2C-D", "E2C-E", "E2C-F"):
            self.assertIn(lane, doc, f"closeout doc must mention {lane}")

    def test_doc_states_closed_after_commit_and_tag(self):
        doc = self._doc()
        self.assertTrue(
            "committed" in doc.lower() or "commit" in doc.lower(),
            "closeout doc must state E2C closed after commit/tag",
        )

    def test_doc_mentions_hard_locks(self):
        doc = self._doc()
        self.assertIn("hard_lock", doc.lower().replace("-", "_").replace(" ", "_"))

    def test_doc_mentions_ready_for_operator_decision(self):
        doc = self._doc()
        self.assertIn("READY_FOR_OPERATOR_DECISION", doc)

    def test_doc_states_no_real_source_fetching(self):
        doc = self._doc()
        self.assertTrue(
            "source fetch" in doc.lower() or "source_fetching" in doc.lower(),
            "closeout doc must mention source fetching restriction",
        )


if __name__ == "__main__":
    unittest.main()
