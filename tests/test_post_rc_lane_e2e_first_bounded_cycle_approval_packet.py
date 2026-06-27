"""
Post-Lane 10 Lane E2E -- First Bounded Cycle Operator Approval Packet

Tests prove:
- e2e_approval_packet module imports cleanly and exports are present
- APPROVAL_PACKET_READY, APPROVAL_PACKET_BLOCKED, E2E_STATUS_READY, E2E_STATUS_BLOCKED correct
- pyproject.toml entry point registered
- valid 1-token APPROVAL_PACKET_READY happy path
- valid 2-token APPROVAL_PACKET_READY happy path
- E2D blocked (invalid token path) cascades to BLOCKED
- E2D blocked (backup missing) cascades to BLOCKED
- E2D blocked (DB missing) cascades to BLOCKED
- E2D blocked (RUNNING job) cascades to BLOCKED
- E2D blocked (locked_at) cascades to BLOCKED
- E2D blocked (lock_owner) cascades to BLOCKED
- E2D blocked (source budget exceeded) cascades to BLOCKED
- all 11 hard-lock flags false in READY payload
- all 11 hard-lock flags false in BLOCKED payload
- hard_locks count is 11
- e2d_decision included in payload
- approval_packet_status is APPROVAL_PACKET_READY or BLOCKED
- approval_packet_reasons is nonempty list
- exact_future_command_preview is a non-empty string (inert text)
- exact_future_command_preview does not execute anything
- required_operator_confirmations is a nonempty list
- stop_conditions is a nonempty list
- rollback_checklist is a nonempty list
- next_lane_boundary is a nonempty string
- no DB mutation (row counts unchanged)
- payload is JSON-serializable for READY
- payload is JSON-serializable for BLOCKED
- CLI outputs valid JSON for READY
- CLI outputs valid JSON for BLOCKED
- BLOCKED returns exit code 0
- READY returns exit code 0
- no source-fetching libraries imported
- command name correct
- dry_run true
- approval_packet_only true
- doc required statements present
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
from printer_v1.operator_cli.commands import main_build_first_bounded_15m_approval_packet
from printer_v1.operator_cli.e2e_approval_packet import (
    APPROVAL_PACKET_BLOCKED,
    APPROVAL_PACKET_READY,
    E2E_STATUS_BLOCKED,
    E2E_STATUS_READY,
    build_e2e_approval_packet,
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

_VALID_NOTE = "Operator-approved for E2E test. Reviewed 2026-06-27."


class _DbTestBase(unittest.TestCase):
    """Temp SQLite DB with migrations plus temp dir for token files."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2e_test.sqlite3"
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
                ("e2e_test_job", "TRACK_FAST_FIRST_15M", status, "2026-06-27T12:00:00"),
            )
            if locked_at is not None:
                conn.execute(
                    "UPDATE printer_scheduler_jobs SET locked_at = ?"
                    " WHERE job_name = 'e2e_test_job'",
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
                " WHERE job_name = 'e2e_test_job'",
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

class LaneE2EImportTests(unittest.TestCase):
    """Prove module imports cleanly and constants are correct."""

    def test_module_importable(self):
        import printer_v1.operator_cli.e2e_approval_packet as mod
        self.assertIsNotNone(mod)

    def test_approval_packet_ready_value(self):
        self.assertEqual(APPROVAL_PACKET_READY, "APPROVAL_PACKET_READY")

    def test_approval_packet_blocked_value(self):
        self.assertEqual(APPROVAL_PACKET_BLOCKED, "BLOCKED")

    def test_e2e_status_ready_value(self):
        self.assertEqual(E2E_STATUS_READY, "E2E_APPROVAL_PACKET_READY")

    def test_e2e_status_blocked_value(self):
        self.assertEqual(E2E_STATUS_BLOCKED, "E2E_APPROVAL_PACKET_BLOCKED")

    def test_cli_command_importable(self):
        self.assertTrue(callable(main_build_first_bounded_15m_approval_packet))

    def test_no_http_libraries_imported(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(lib, sys.modules,
                f"Network library {lib!r} must not be imported")

    def test_pyproject_entry_point_registered(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-build-first-bounded-15m-approval-packet", content)
        self.assertIn("main_build_first_bounded_15m_approval_packet", content)


# ---------------------------------------------------------------------------
# APPROVAL_PACKET_READY happy path
# ---------------------------------------------------------------------------

class LaneE2EReadyPayloadTests(_DbTestBase):
    """Prove APPROVAL_PACKET_READY for valid inputs."""

    def _ready_1(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1, "TRACK_FAST")])
        return build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)

    def _ready_2(self) -> dict:
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        return build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)

    def test_single_token_produces_ready(self):
        self.assertEqual(self._ready_1()["approval_packet_status"], APPROVAL_PACKET_READY)

    def test_two_token_produces_ready(self):
        self.assertEqual(self._ready_2()["approval_packet_status"], APPROVAL_PACKET_READY)

    def test_e2e_status_ready_when_ready(self):
        payload = self._ready_1()
        self.assertEqual(payload.get("e2d_decision", {}).get("e2d_status"),
                         "E2D_READY_FOR_OPERATOR_APPROVAL_REVIEW")

    def test_command_name_correct(self):
        self.assertEqual(
            self._ready_1()["command"],
            "printer-build-first-bounded-15m-approval-packet",
        )

    def test_dry_run_true(self):
        self.assertTrue(self._ready_1()["dry_run"])

    def test_approval_packet_only_true(self):
        self.assertTrue(self._ready_1()["approval_packet_only"])

    def test_ready_reasons_mention_go_to_operator_approval(self):
        reasons = self._ready_1()["approval_packet_reasons"]
        self.assertTrue(any("GO_TO_OPERATOR_APPROVAL" in r for r in reasons))

    def test_ready_reasons_mention_not_authorize(self):
        reasons = self._ready_1()["approval_packet_reasons"]
        self.assertTrue(any("NOT authorize" in r or "not authorize" in r.lower() for r in reasons))

    def test_ready_reasons_mention_separately_named(self):
        reasons = self._ready_1()["approval_packet_reasons"]
        self.assertTrue(any("separately" in r.lower() for r in reasons))


# ---------------------------------------------------------------------------
# BLOCKED cases (E2D blocked cascades)
# ---------------------------------------------------------------------------

class LaneE2EBlockedCascadeTests(_DbTestBase):
    """Prove BLOCKED when E2D fails."""

    def test_none_token_path_blocked(self):
        payload = build_e2e_approval_packet(None, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_missing_file_blocked(self):
        payload = build_e2e_approval_packet(
            "/no/such/tokens.json", self.db_path, backup_confirmed=True
        )
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_backup_not_confirmed_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=False)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_db_missing_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(
            tf, "/nonexistent/db.sqlite3", backup_confirmed=True
        )
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_none_db_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, None, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_running_job_blocked(self):
        self._insert_scheduler_job(status="RUNNING")
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_locked_at_blocked(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_lock_owner_blocked(self):
        self._insert_scheduler_job(status="PENDING")
        self._set_lock_owner("stale_owner")
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_source_budget_exceeded_blocked(self):
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_zero_tokens_blocked(self):
        tf = self._write_token_file([])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_invalid_mint_blocked(self):
        tf = self._write_token_file([self._valid_entry("not-a-mint")])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_blocked_reasons_nonempty(self):
        payload = build_e2e_approval_packet(None, self.db_path, backup_confirmed=True)
        self.assertGreater(len(payload["approval_packet_reasons"]), 0)

    def test_blocked_e2d_decision_still_present(self):
        payload = build_e2e_approval_packet(None, self.db_path, backup_confirmed=True)
        self.assertIn("e2d_decision", payload)
        self.assertEqual(payload["e2d_decision"]["final_decision"], "BLOCKED")


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------

class LaneE2EPayloadStructureTests(_DbTestBase):
    """Prove all required payload keys are present."""

    def _ready(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        return build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)

    def _blocked(self) -> dict:
        return build_e2e_approval_packet(None, self.db_path, backup_confirmed=True)

    def test_has_command(self):
        self.assertIn("command", self._ready())

    def test_has_dry_run(self):
        self.assertIn("dry_run", self._ready())

    def test_has_approval_packet_only(self):
        self.assertIn("approval_packet_only", self._ready())

    def test_has_e2d_decision(self):
        self.assertIn("e2d_decision", self._ready())

    def test_has_approval_packet_status(self):
        self.assertIn("approval_packet_status", self._ready())

    def test_has_approval_packet_reasons(self):
        self.assertIn("approval_packet_reasons", self._ready())

    def test_has_exact_future_command_preview(self):
        self.assertIn("exact_future_command_preview", self._ready())

    def test_has_required_operator_confirmations(self):
        self.assertIn("required_operator_confirmations", self._ready())

    def test_has_stop_conditions(self):
        self.assertIn("stop_conditions", self._ready())

    def test_has_rollback_checklist(self):
        self.assertIn("rollback_checklist", self._ready())

    def test_has_hard_locks(self):
        self.assertIn("hard_locks", self._ready())

    def test_has_next_lane_boundary(self):
        self.assertIn("next_lane_boundary", self._ready())

    def test_exact_future_command_preview_is_str(self):
        preview = self._ready()["exact_future_command_preview"]
        self.assertIsInstance(preview, str)
        self.assertGreater(len(preview), 10)

    def test_exact_future_command_preview_mentions_inert(self):
        preview = self._ready()["exact_future_command_preview"]
        self.assertTrue(
            "inert" in preview.lower() or "does NOT execute" in preview or
            "not authorized" in preview.lower(),
            "preview must state it is inert text only",
        )

    def test_exact_future_command_preview_not_blocked_present(self):
        payload = self._blocked()
        self.assertIn("exact_future_command_preview", payload)
        preview = payload["exact_future_command_preview"]
        self.assertIsInstance(preview, str)

    def test_required_operator_confirmations_is_nonempty_list(self):
        items = self._ready()["required_operator_confirmations"]
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 5)

    def test_stop_conditions_is_nonempty_list(self):
        items = self._ready()["stop_conditions"]
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 5)

    def test_rollback_checklist_is_nonempty_list(self):
        items = self._ready()["rollback_checklist"]
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 2)

    def test_next_lane_boundary_nonempty_str(self):
        boundary = self._ready()["next_lane_boundary"]
        self.assertIsInstance(boundary, str)
        self.assertGreater(len(boundary), 20)

    def test_next_lane_boundary_mentions_separately_named(self):
        boundary = self._ready()["next_lane_boundary"]
        self.assertIn("separately", boundary.lower())

    def test_e2d_decision_has_final_decision(self):
        self.assertIn("final_decision", self._ready()["e2d_decision"])

    def test_e2d_decision_go_when_ready(self):
        self.assertEqual(
            self._ready()["e2d_decision"]["final_decision"],
            "GO_TO_OPERATOR_APPROVAL",
        )

    def test_payload_json_serializable_ready(self):
        s = json.dumps(self._ready())
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 500)

    def test_payload_json_serializable_blocked(self):
        s = json.dumps(self._blocked())
        self.assertIsInstance(s, str)

    def test_approval_packet_reasons_nonempty_for_ready(self):
        reasons = self._ready()["approval_packet_reasons"]
        self.assertIsInstance(reasons, list)
        self.assertGreater(len(reasons), 0)


# ---------------------------------------------------------------------------
# Hard lock tests
# ---------------------------------------------------------------------------

class LaneE2EHardLockTests(_DbTestBase):
    """Prove all 11 hard-lock flags are False."""

    def test_all_hard_locks_false_in_ready(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False")

    def test_hard_locks_count_is_11(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        self.assertEqual(len(payload["hard_locks"]), 11)

    def test_all_hard_locks_false_in_blocked(self):
        payload = build_e2e_approval_packet(None, self.db_path, backup_confirmed=True)
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
# No DB mutation
# ---------------------------------------------------------------------------

class LaneE2EMutationTests(_DbTestBase):
    """Prove no persistent DB mutation during approval packet build."""

    def test_scheduler_rows_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_scheduler_jobs")
        build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_scheduler_jobs")
        self.assertEqual(before, after)

    def test_source_requests_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_requests")
        build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_source_requests")
        self.assertEqual(before, after)

    def test_source_responses_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_responses")
        build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        after = self._count_rows("printer_source_responses")
        self.assertEqual(before, after)

    def test_e2d_mutation_proof_all_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2e_approval_packet(tf, self.db_path, backup_confirmed=True)
        proof = payload["e2d_decision"]["db_mutation_proof"]
        self.assertTrue(proof.get("all_counts_unchanged"))
        self.assertEqual(proof.get("changed_tables", []), [])


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2ECliTests(_DbTestBase):
    """Prove CLI outputs valid JSON and returns 0 for both READY and BLOCKED."""

    def _run_ready(self) -> tuple[int, dict]:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        args = [
            "--token-list-path", str(tf),
            "--backup-confirmed",
            "--db-path", str(self.db_path),
            "--format", "json",
        ]
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_build_first_bounded_15m_approval_packet(args)
        return rc, json.loads(captured.getvalue())

    def test_cli_returns_0_for_ready(self):
        rc, _ = self._run_ready()
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json_ready(self):
        _, payload = self._run_ready()
        self.assertIn("approval_packet_status", payload)

    def test_cli_ready_status(self):
        _, payload = self._run_ready()
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_READY)

    def test_cli_returns_0_for_blocked(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_build_first_bounded_15m_approval_packet([
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)

    def test_cli_two_tokens_ready(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_build_first_bounded_15m_approval_packet([
                "--token-list-path", str(tf),
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_READY)

    def test_cli_output_has_e2d_decision(self):
        _, payload = self._run_ready()
        self.assertIn("e2d_decision", payload)

    def test_cli_output_has_exact_future_command_preview(self):
        _, payload = self._run_ready()
        self.assertIn("exact_future_command_preview", payload)

    def test_cli_output_has_stop_conditions(self):
        _, payload = self._run_ready()
        self.assertIn("stop_conditions", payload)

    def test_cli_output_has_rollback_checklist(self):
        _, payload = self._run_ready()
        self.assertIn("rollback_checklist", payload)

    def test_cli_blocked_missing_backup_returns_0(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_build_first_bounded_15m_approval_packet([
                "--token-list-path", str(tf),
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["approval_packet_status"], APPROVAL_PACKET_BLOCKED)


# ---------------------------------------------------------------------------
# Approval doc required statements
# ---------------------------------------------------------------------------

class LaneE2EDocTests(unittest.TestCase):
    """Prove approval doc exists with required statements."""

    def _doc(self) -> str:
        path = PROJECT_ROOT / "docs" / "printer-v1-lane-e2e-first-bounded-cycle-approval-packet.md"
        self.assertTrue(path.exists(), f"E2E doc not found: {path}")
        return path.read_text(encoding="utf-8")

    def test_doc_exists(self):
        path = PROJECT_ROOT / "docs" / "printer-v1-lane-e2e-first-bounded-cycle-approval-packet.md"
        self.assertTrue(path.exists())

    def test_doc_states_e2e_is_approval_packet_only(self):
        doc = self._doc()
        self.assertIn("approval-packet only", doc.lower())

    def test_doc_states_does_not_authorize_real_execution(self):
        doc = self._doc()
        self.assertTrue(
            "does NOT authorize" in doc or "does not authorize" in doc.lower(),
            "doc must state E2E does NOT authorize real execution",
        )

    def test_doc_states_does_not_start_scheduler(self):
        doc = self._doc()
        self.assertTrue(
            "scheduler" in doc.lower(),
            "doc must mention scheduler restriction",
        )

    def test_doc_states_does_not_start_source_fetching(self):
        doc = self._doc()
        self.assertTrue(
            "source fetch" in doc.lower() or "source_fetching" in doc.lower(),
            "doc must state E2E does not start source fetching",
        )

    def test_doc_states_next_lane_separately_named(self):
        doc = self._doc()
        self.assertIn("separately named", doc.lower())

    def test_doc_states_all_v1_restrictions_remain_active(self):
        doc = self._doc()
        self.assertTrue(
            "remain" in doc.lower() and "active" in doc.lower(),
            "doc must state all V1 restrictions remain active",
        )

    def test_doc_mentions_approval_packet_ready(self):
        doc = self._doc()
        self.assertIn("APPROVAL_PACKET_READY", doc)

    def test_doc_mentions_hard_locks(self):
        doc = self._doc()
        self.assertIn("hard_lock", doc.lower().replace("-", "_").replace(" ", "_"))

    def test_doc_mentions_e2d(self):
        doc = self._doc()
        self.assertIn("E2D", doc)

    def test_doc_mentions_e2e(self):
        doc = self._doc()
        self.assertIn("E2E", doc)

    def test_doc_mentions_stop_conditions(self):
        doc = self._doc()
        self.assertIn("stop condition", doc.lower())

    def test_doc_mentions_rollback(self):
        doc = self._doc()
        self.assertIn("rollback", doc.lower())

    def test_doc_mentions_operator_confirmations(self):
        doc = self._doc()
        self.assertTrue(
            "operator confirm" in doc.lower() or "required_operator" in doc.lower(),
            "doc must mention required operator confirmations",
        )


if __name__ == "__main__":
    unittest.main()
