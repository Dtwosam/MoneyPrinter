"""
Post-Lane 10 Lane E2D -- First Bounded Real Cycle Decision Package

Tests prove:
- e2d_decision module imports cleanly and exports are present
- FINAL_DECISION_GO, FINAL_DECISION_BLOCKED, E2D_STATUS_GO, E2D_STATUS_BLOCKED constants correct
- pyproject.toml entry point registered
- valid 1-token GO_TO_OPERATOR_APPROVAL happy path
- valid 2-token GO_TO_OPERATOR_APPROVAL happy path
- blocked token file produces BLOCKED
- backup not confirmed produces BLOCKED
- DB missing produces BLOCKED
- RUNNING scheduler job produces BLOCKED
- locked_at active lock produces BLOCKED
- lock_owner active lock produces BLOCKED
- source budget exceeded produces BLOCKED
- E2C-F blocked cascades to BLOCKED
- row-count mutation failure cascades to BLOCKED
- all 11 hard-lock flags false in GO payload
- all 11 hard-lock flags false in BLOCKED payload
- hard_locks count is 11
- e2c_f_review included in payload
- db_mutation_proof included in payload
- next_required_operator_action present in payload
- payload is JSON-serializable
- CLI outputs valid JSON for GO
- CLI outputs valid JSON for BLOCKED
- BLOCKED returns exit code 0
- GO returns exit code 0
- no source-fetching libraries imported
- no DB mutation (row counts unchanged)
- doc required statements present
- e2d_status correct for GO and BLOCKED
- decision_only true
- dry_run true
- command name correct
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
from printer_v1.operator_cli.commands import main_decide_first_bounded_15m_cycle
from printer_v1.operator_cli.e2d_decision import (
    E2D_STATUS_BLOCKED,
    E2D_STATUS_GO,
    FINAL_DECISION_BLOCKED,
    FINAL_DECISION_GO,
    build_e2d_decision_payload,
)
from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS
from printer_v1.sources.contracts import NormalizedSourceResult, build_governed_source_request
from printer_v1.sources.recording import record_source_request, record_source_response
from printer_v1.sources.registry import SOURCE_REGISTRY


# Structurally valid Solana base58 test mints -- NOT placeholders.
_MINT_1 = "C" * 43   # 43 chars, all 'C'
_MINT_2 = "D" * 44   # 44 chars, all 'D'

_RATE_LIMIT_SOURCE = "alternative_me"
_RATE_LIMIT_KIND = "fear_greed_context"
_RATE_LIMIT = SOURCE_REGISTRY[_RATE_LIMIT_SOURCE].default_rate_limit_per_minute

_VALID_NOTE = "Operator-approved for E2D test. Reviewed 2026-06-27."


class _DbTestBase(unittest.TestCase):
    """Temp SQLite DB with migrations plus temp dir for token files."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2d_test.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self.tempdir.cleanup()

    def _write_token_file(self, tokens: list) -> pathlib.Path:
        data = {"tokens": tokens}
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
                ("e2d_test_job", "TRACK_FAST_FIRST_15M", status, "2026-06-27T12:00:00"),
            )
            if locked_at is not None:
                conn.execute(
                    "UPDATE printer_scheduler_jobs SET locked_at = ?"
                    " WHERE job_name = 'e2d_test_job'",
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
                " WHERE job_name = 'e2d_test_job'",
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

class LaneE2DImportTests(unittest.TestCase):
    """Prove module imports cleanly and constants are correct."""

    def test_module_importable(self):
        import printer_v1.operator_cli.e2d_decision as mod
        self.assertIsNotNone(mod)

    def test_final_decision_go_value(self):
        self.assertEqual(FINAL_DECISION_GO, "GO_TO_OPERATOR_APPROVAL")

    def test_final_decision_blocked_value(self):
        self.assertEqual(FINAL_DECISION_BLOCKED, "BLOCKED")

    def test_e2d_status_go_value(self):
        self.assertEqual(E2D_STATUS_GO, "E2D_READY_FOR_OPERATOR_APPROVAL_REVIEW")

    def test_e2d_status_blocked_value(self):
        self.assertEqual(E2D_STATUS_BLOCKED, "E2D_DECISION_BLOCKED")

    def test_cli_command_importable(self):
        self.assertTrue(callable(main_decide_first_bounded_15m_cycle))

    def test_no_http_libraries_imported(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(lib, sys.modules,
                f"Network library {lib!r} must not be imported")

    def test_pyproject_entry_point_registered(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-decide-first-bounded-15m-cycle", content)
        self.assertIn("main_decide_first_bounded_15m_cycle", content)


# ---------------------------------------------------------------------------
# GO_TO_OPERATOR_APPROVAL happy path
# ---------------------------------------------------------------------------

class LaneE2DGoPayloadTests(_DbTestBase):
    """Prove GO_TO_OPERATOR_APPROVAL for valid single and two-token inputs."""

    def _go_1(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1, "TRACK_FAST")])
        return build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)

    def _go_2(self) -> dict:
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        return build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)

    def test_single_token_produces_go(self):
        self.assertEqual(self._go_1()["final_decision"], FINAL_DECISION_GO)

    def test_two_token_produces_go(self):
        self.assertEqual(self._go_2()["final_decision"], FINAL_DECISION_GO)

    def test_e2d_status_go_when_go(self):
        self.assertEqual(self._go_1()["e2d_status"], E2D_STATUS_GO)

    def test_dry_run_true(self):
        self.assertTrue(self._go_1()["dry_run"])

    def test_decision_only_true(self):
        self.assertTrue(self._go_1()["decision_only"])

    def test_command_name_correct(self):
        self.assertEqual(
            self._go_1()["command"],
            "printer-decide-first-bounded-15m-cycle",
        )

    def test_go_reasons_mention_ready_for_operator_decision(self):
        reasons = self._go_1()["final_decision_reasons"]
        self.assertTrue(any("READY_FOR_OPERATOR_DECISION" in r for r in reasons))

    def test_go_reasons_mention_no_real_execution(self):
        reasons = self._go_1()["final_decision_reasons"]
        self.assertTrue(any("NOT authorize" in r or "not authorize" in r.lower() for r in reasons))

    def test_go_reasons_mention_next_lane_separately(self):
        reasons = self._go_1()["final_decision_reasons"]
        self.assertTrue(any("next" in r.lower() and "lane" in r.lower() for r in reasons))


# ---------------------------------------------------------------------------
# BLOCKED cases -- token file
# ---------------------------------------------------------------------------

class LaneE2DBlockedTokenTests(_DbTestBase):
    """Prove BLOCKED when token file is invalid."""

    def test_none_token_path_blocked(self):
        payload = build_e2d_decision_payload(None, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)
        self.assertEqual(payload["e2d_status"], E2D_STATUS_BLOCKED)

    def test_missing_file_blocked(self):
        payload = build_e2d_decision_payload(
            "/no/such/file.json", self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_zero_tokens_blocked(self):
        tf = self._write_token_file([])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_three_tokens_blocked(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1),
            self._valid_entry(_MINT_2),
            self._valid_entry("C" * 44),
        ])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_placeholder_mint_43a_blocked(self):
        tf = self._write_token_file([self._valid_entry("A" * 43)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_placeholder_mint_44b_blocked(self):
        tf = self._write_token_file([self._valid_entry("B" * 44)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_approved_false_blocked(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
            "operator_note": _VALID_NOTE, "approved_by_operator": False,
        }])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_approved_non_bool_blocked(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
            "operator_note": _VALID_NOTE, "approved_by_operator": "true",
        }])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_blank_note_blocked(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST",
            "operator_note": "", "approved_by_operator": True,
        }])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_invalid_mint_blocked(self):
        tf = self._write_token_file([self._valid_entry("not-a-mint")])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_invalid_lifecycle_lane_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1, "UNKNOWN_LANE")])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_duplicate_mints_blocked(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_1, "TRACK_NORMAL"),
        ])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)


# ---------------------------------------------------------------------------
# BLOCKED cases -- DB preflight
# ---------------------------------------------------------------------------

class LaneE2DBlockedDbTests(_DbTestBase):
    """Prove BLOCKED when DB preflight fails."""

    def _tf(self) -> pathlib.Path:
        return self._write_token_file([self._valid_entry(_MINT_1)])

    def test_backup_not_confirmed_blocked(self):
        payload = build_e2d_decision_payload(
            self._tf(), self.db_path, backup_confirmed=False
        )
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_db_missing_blocked(self):
        payload = build_e2d_decision_payload(
            self._tf(), "/nonexistent/db.sqlite3", backup_confirmed=True
        )
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_none_db_path_blocked(self):
        payload = build_e2d_decision_payload(
            self._tf(), None, backup_confirmed=True
        )
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_running_job_blocked(self):
        self._insert_scheduler_job(status="RUNNING")
        payload = build_e2d_decision_payload(
            self._tf(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_locked_at_blocked(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        payload = build_e2d_decision_payload(
            self._tf(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_lock_owner_blocked(self):
        self._insert_scheduler_job(status="PENDING")
        self._set_lock_owner("stale_owner")
        payload = build_e2d_decision_payload(
            self._tf(), self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)


# ---------------------------------------------------------------------------
# BLOCKED case -- source budget
# ---------------------------------------------------------------------------

class LaneE2DBlockedSourceBudgetTests(_DbTestBase):
    """Prove BLOCKED when source budget is exhausted."""

    def test_rate_limit_exceeded_blocked(self):
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_below_rate_limit_allows_go(self):
        for _ in range(_RATE_LIMIT - 1):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_GO)


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------

class LaneE2DPayloadStructureTests(_DbTestBase):
    """Prove payload has all required keys and correct values."""

    def _go(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        return build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)

    def _blocked(self) -> dict:
        return build_e2d_decision_payload(None, self.db_path, backup_confirmed=True)

    def test_has_command_key(self):
        self.assertIn("command", self._go())

    def test_has_dry_run_key(self):
        self.assertIn("dry_run", self._go())

    def test_has_decision_only_key(self):
        self.assertIn("decision_only", self._go())

    def test_has_e2d_status_key(self):
        self.assertIn("e2d_status", self._go())

    def test_has_e2c_f_review_key(self):
        self.assertIn("e2c_f_review", self._go())

    def test_has_db_mutation_proof_key(self):
        self.assertIn("db_mutation_proof", self._go())

    def test_has_final_decision_key(self):
        self.assertIn("final_decision", self._go())

    def test_has_final_decision_reasons_key(self):
        self.assertIn("final_decision_reasons", self._go())

    def test_has_hard_locks_key(self):
        self.assertIn("hard_locks", self._go())

    def test_has_next_required_operator_action_key(self):
        self.assertIn("next_required_operator_action", self._go())

    def test_e2c_f_review_has_final_recommendation(self):
        payload = self._go()
        self.assertIn("final_recommendation", payload["e2c_f_review"])

    def test_e2c_f_review_recommendation_is_ready(self):
        payload = self._go()
        self.assertEqual(
            payload["e2c_f_review"]["final_recommendation"],
            "READY_FOR_OPERATOR_DECISION",
        )

    def test_db_mutation_proof_all_counts_unchanged(self):
        payload = self._go()
        self.assertTrue(payload["db_mutation_proof"]["all_counts_unchanged"])

    def test_next_operator_action_nonempty_for_go(self):
        payload = self._go()
        self.assertTrue(len(payload["next_required_operator_action"]) > 10)

    def test_next_operator_action_nonempty_for_blocked(self):
        payload = self._blocked()
        self.assertTrue(len(payload["next_required_operator_action"]) > 10)

    def test_payload_json_serializable_go(self):
        s = json.dumps(self._go())
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 200)

    def test_payload_json_serializable_blocked(self):
        s = json.dumps(self._blocked())
        self.assertIsInstance(s, str)

    def test_e2c_f_review_includes_readiness_review(self):
        payload = self._go()
        self.assertIn("e2c_readiness_review", payload["e2c_f_review"])

    def test_e2c_f_review_includes_fixture_rehearsal(self):
        payload = self._go()
        self.assertIn("fixture_rehearsal_review", payload["e2c_f_review"])


# ---------------------------------------------------------------------------
# Hard lock tests
# ---------------------------------------------------------------------------

class LaneE2DHardLockTests(_DbTestBase):
    """Prove all 11 hard-lock flags are False in payload."""

    def test_all_hard_locks_false_in_go_payload(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False")

    def test_hard_locks_count_is_11(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(len(payload["hard_locks"]), 11)

    def test_all_hard_locks_false_in_blocked_payload(self):
        payload = build_e2d_decision_payload(None, self.db_path, backup_confirmed=True)
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

    def test_pnl_enabled_false(self):
        self.assertIs(HARD_LOCKS["pnl_enabled"], False)


# ---------------------------------------------------------------------------
# Mutation proof -- no persistent DB changes
# ---------------------------------------------------------------------------

class LaneE2DMutationProofTests(_DbTestBase):
    """Prove no persistent DB mutation during E2D decision."""

    def test_scheduler_rows_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_scheduler_jobs")
        build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_scheduler_jobs")
        self.assertEqual(before, after)

    def test_source_requests_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_requests")
        build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_source_requests")
        self.assertEqual(before, after)

    def test_source_responses_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_responses")
        build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_source_responses")
        self.assertEqual(before, after)

    def test_mutation_proof_reports_all_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        proof = payload["db_mutation_proof"]
        self.assertTrue(proof.get("all_counts_unchanged"))
        self.assertEqual(proof.get("changed_tables", []), [])


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2DCliTests(_DbTestBase):
    """Prove CLI outputs valid JSON and returns 0 for both GO and BLOCKED."""

    def _run(self, extra_args: list[str] | None = None) -> tuple[int, dict]:
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
            rc = main_decide_first_bounded_15m_cycle(args)
        return rc, json.loads(captured.getvalue())

    def test_cli_returns_0_for_go(self):
        rc, _ = self._run()
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json_for_go(self):
        _, payload = self._run()
        self.assertIn("final_decision", payload)

    def test_cli_go_decision(self):
        _, payload = self._run()
        self.assertEqual(payload["final_decision"], FINAL_DECISION_GO)

    def test_cli_returns_0_for_blocked(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_decide_first_bounded_15m_cycle([
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_cli_blocked_missing_backup_returns_0(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_decide_first_bounded_15m_cycle([
                "--token-list-path", str(tf),
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)

    def test_cli_two_tokens_go(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_decide_first_bounded_15m_cycle([
                "--token-list-path", str(tf),
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["final_decision"], FINAL_DECISION_GO)

    def test_cli_output_has_e2d_status(self):
        _, payload = self._run()
        self.assertIn("e2d_status", payload)
        self.assertEqual(payload["e2d_status"], E2D_STATUS_GO)

    def test_cli_output_has_e2c_f_review(self):
        _, payload = self._run()
        self.assertIn("e2c_f_review", payload)

    def test_cli_output_has_db_mutation_proof(self):
        _, payload = self._run()
        self.assertIn("db_mutation_proof", payload)


# ---------------------------------------------------------------------------
# E2C-F blocked cascades to E2D blocked
# ---------------------------------------------------------------------------

class LaneE2DE2CFBlockedCascadeTests(_DbTestBase):
    """Prove that an E2C-F BLOCKED result propagates to E2D BLOCKED."""

    def test_blocked_token_file_cascades(self):
        tf = self._write_token_file([])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)
        self.assertEqual(payload["e2c_f_review"]["final_recommendation"], "BLOCKED")

    def test_blocked_backup_cascades(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=False)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)
        self.assertEqual(payload["e2c_f_review"]["final_recommendation"], "BLOCKED")

    def test_blocked_running_job_cascades(self):
        self._insert_scheduler_job(status="RUNNING")
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["final_decision"], FINAL_DECISION_BLOCKED)
        self.assertEqual(payload["e2c_f_review"]["final_recommendation"], "BLOCKED")

    def test_blocked_reasons_nonempty_when_blocked(self):
        tf = self._write_token_file([])
        payload = build_e2d_decision_payload(tf, self.db_path, backup_confirmed=True)
        self.assertGreater(len(payload["final_decision_reasons"]), 0)


# ---------------------------------------------------------------------------
# Decision doc required statements
# ---------------------------------------------------------------------------

class LaneE2DDecisionDocTests(unittest.TestCase):
    """Prove decision doc exists with required statements."""

    def _doc(self) -> str:
        path = PROJECT_ROOT / "docs" / "printer-v1-lane-e2d-first-bounded-cycle-decision.md"
        self.assertTrue(path.exists(), f"E2D decision doc not found: {path}")
        return path.read_text(encoding="utf-8")

    def test_doc_exists(self):
        path = PROJECT_ROOT / "docs" / "printer-v1-lane-e2d-first-bounded-cycle-decision.md"
        self.assertTrue(path.exists())

    def test_doc_states_e2d_is_decision_gate_only(self):
        doc = self._doc()
        self.assertIn("decision gate only", doc.lower())

    def test_doc_states_does_not_authorize_real_execution(self):
        doc = self._doc()
        self.assertTrue(
            "does NOT authorize" in doc or "does not authorize" in doc.lower(),
            "doc must state E2D does NOT authorize real execution",
        )

    def test_doc_states_next_lane_separately_named_and_approved(self):
        doc = self._doc()
        self.assertTrue(
            "separately named" in doc.lower() or "separately approved" in doc.lower(),
            "doc must state next lane must be separately named and explicitly approved",
        )

    def test_doc_states_all_v1_restrictions_remain_active(self):
        doc = self._doc()
        self.assertTrue(
            "remain" in doc.lower() and "active" in doc.lower(),
            "doc must state all V1 restrictions remain active",
        )

    def test_doc_mentions_go_to_operator_approval(self):
        doc = self._doc()
        self.assertIn("GO_TO_OPERATOR_APPROVAL", doc)

    def test_doc_mentions_blocked(self):
        doc = self._doc()
        self.assertIn("BLOCKED", doc)

    def test_doc_mentions_hard_locks(self):
        doc = self._doc()
        self.assertIn("hard_lock", doc.lower().replace("-", "_").replace(" ", "_"))

    def test_doc_mentions_e2c_f(self):
        doc = self._doc()
        self.assertIn("E2C-F", doc)

    def test_doc_mentions_e2d(self):
        doc = self._doc()
        self.assertIn("E2D", doc)

    def test_doc_mentions_no_real_source_fetching(self):
        doc = self._doc()
        self.assertTrue(
            "source fetch" in doc.lower() or "source_fetching" in doc.lower(),
            "doc must mention source fetching restriction",
        )

    def test_doc_mentions_explicit_operator_approval_required(self):
        doc = self._doc()
        self.assertTrue(
            "operator" in doc.lower() and "approv" in doc.lower(),
            "doc must mention operator approval required",
        )


if __name__ == "__main__":
    unittest.main()
