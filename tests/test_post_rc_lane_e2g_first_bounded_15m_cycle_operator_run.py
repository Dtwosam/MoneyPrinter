"""
Post-Lane 10 Lane E2G -- First Bounded 15m Cycle Operator Run Boundary

Tests prove:
- e2g_operator_run module imports cleanly and exports are present
- OPERATOR_RUN_READY, OPERATOR_RUN_BLOCKED, E2G_STATUS_READY, E2G_STATUS_BLOCKED correct
- pyproject.toml entry point registered
- runtime path missing -> BLOCKED (real state: no TRACK_FAST_FIRST_15M handler)
- happy fixture run boundary: OPERATOR_RUN_READY when handler is patched present
- invalid token list -> BLOCKED
- missing backup proof -> BLOCKED
- backup_proof_path None -> BLOCKED
- missing backup_confirmed -> BLOCKED
- missing approval_confirmed -> BLOCKED
- DB missing -> BLOCKED
- RUNNING job -> BLOCKED
- active locks (locked_at) -> BLOCKED
- active locks (lock_owner) -> BLOCKED
- source governor denial -> BLOCKED
- token count 2 blocked (E2G first-run constraint requires exactly 1)
- zero tokens blocked
- all 11 hard-lock flags false in OPERATOR_RUN_READY
- all 11 hard-lock flags false in BLOCKED
- hard_locks count is 11
- e2f_execution_boundary included in payload
- first_run_status is OPERATOR_RUN_READY or BLOCKED
- first_run_status_reasons nonempty
- e2g_status correct string
- runtime_path_exists is False in real build
- backup_proof_confirmed reflects file check
- before_db_counts included when DB exists
- before_db_counts has expected tables
- exact_operator_run_command is inert text
- exact_operator_run_command mentions approval-confirmed
- exact_operator_run_command mentions Claude did not run
- allowed_table_deltas is nonempty dict
- allowed_table_deltas mentions printer_source_requests
- allowed_table_deltas mentions printer_memories
- forbidden_table_deltas is nonempty list
- forbidden_table_deltas mentions paper_decisions
- stop_conditions is nonempty list
- stop_conditions mentions runtime handler
- stop_conditions mentions backup proof
- stop_conditions mentions BUY/SELL/HOLD
- stop_conditions mentions 5m support-only
- rollback_checklist is nonempty list
- rollback_checklist items are checkbox format
- next_required_operator_action nonempty
- next_required_operator_action mentions handler when BLOCKED
- planning_only true
- claude_did_not_run_cycle true
- dry_run true
- command name correct
- no DB mutation (row counts unchanged)
- payload JSON-serializable for BLOCKED
- payload JSON-serializable for OPERATOR_RUN_READY (patched)
- CLI outputs valid JSON for BLOCKED
- CLI outputs valid JSON for OPERATOR_RUN_READY (patched)
- CLI BLOCKED returns exit code 0
- CLI OPERATOR_RUN_READY returns exit code 0
- CLI blocked without --backup-proof-path
- CLI blocked without --approval-confirmed
- CLI blocked without --backup-confirmed
- no source-fetching libraries imported
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
from printer_v1.operator_cli.commands import main_run_e2g_first_bounded_15m_operator_run
from printer_v1.operator_cli.e2g_operator_run import (
    OPERATOR_RUN_BLOCKED,
    OPERATOR_RUN_READY,
    E2G_STATUS_BLOCKED,
    E2G_STATUS_READY,
    build_e2g_operator_run_payload,
    _check_15m_cycle_runtime_available,
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

_VALID_NOTE = "Operator-approved for E2G test. Reviewed 2026-06-27."

# Patch target for simulating runtime handler available.
_RUNTIME_CHECK_PATCH = (
    "printer_v1.operator_cli.e2g_operator_run._check_15m_cycle_runtime_available"
)


class _DbTestBase(unittest.TestCase):
    """Temp SQLite DB with migrations plus temp dir for token files."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2g_test.sqlite3"
        apply_migrations(self.db_path)
        # Create a fake backup proof file for tests.
        self.backup_proof_path = pathlib.Path(self.tempdir.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")

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
                ("e2g_test_job", "TRACK_FAST_FIRST_15M", status, "2026-06-27T12:00:00"),
            )
            if locked_at is not None:
                conn.execute(
                    "UPDATE printer_scheduler_jobs SET locked_at = ?"
                    " WHERE job_name = 'e2g_test_job'",
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
                " WHERE job_name = 'e2g_test_job'",
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

    def _blocked(self, **kw) -> dict:
        """Build payload with default BLOCKED-producing inputs."""
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        defaults = dict(
            token_file_path=tf,
            db_path=self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        defaults.update(kw)
        return build_e2g_operator_run_payload(**defaults)

    def _ready(self) -> dict:
        """Build payload with runtime patched to True (happy path)."""
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        with patch(_RUNTIME_CHECK_PATCH, return_value=(True, "")):
            return build_e2g_operator_run_payload(
                tf, self.db_path,
                approval_confirmed=True,
                backup_confirmed=True,
                backup_proof_path=self.backup_proof_path,
            )


# ---------------------------------------------------------------------------
# Import and constant tests
# ---------------------------------------------------------------------------

class LaneE2GImportTests(unittest.TestCase):
    """Prove module imports cleanly and constants are correct."""

    def test_module_importable(self):
        import printer_v1.operator_cli.e2g_operator_run as mod
        self.assertIsNotNone(mod)

    def test_operator_run_ready_value(self):
        self.assertEqual(OPERATOR_RUN_READY, "OPERATOR_RUN_READY")

    def test_operator_run_blocked_value(self):
        self.assertEqual(OPERATOR_RUN_BLOCKED, "BLOCKED")

    def test_e2g_status_ready_value(self):
        self.assertEqual(E2G_STATUS_READY, "E2G_OPERATOR_RUN_READY")

    def test_e2g_status_blocked_value(self):
        self.assertEqual(E2G_STATUS_BLOCKED, "E2G_OPERATOR_RUN_BLOCKED")

    def test_cli_command_importable(self):
        self.assertTrue(callable(main_run_e2g_first_bounded_15m_operator_run))

    def test_no_http_libraries_imported(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(lib, sys.modules,
                f"Network library {lib!r} must not be imported")

    def test_pyproject_entry_point_registered(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-run-e2g-first-bounded-15m-operator-run", content)
        self.assertIn("main_run_e2g_first_bounded_15m_operator_run", content)


# ---------------------------------------------------------------------------
# Runtime path discovery tests
# ---------------------------------------------------------------------------

class LaneE2GRuntimePathTests(unittest.TestCase):
    """Prove runtime path discovery returns correct result."""

    def test_runtime_not_available_in_real_build(self):
        available, reason = _check_15m_cycle_runtime_available()
        self.assertFalse(available)

    def test_runtime_reason_mentions_handler(self):
        _, reason = _check_15m_cycle_runtime_available()
        self.assertTrue(
            "TRACK_FAST_FIRST_15M" in reason or "handler" in reason.lower(),
            "reason must mention missing handler",
        )

    def test_runtime_reason_mentions_phase35(self):
        _, reason = _check_15m_cycle_runtime_available()
        self.assertTrue(
            "Phase 35" in reason or "BACKUP_SOURCE_CHECK" in reason,
            "reason must mention Phase 35 or BACKUP_SOURCE_CHECK",
        )


# ---------------------------------------------------------------------------
# BLOCKED: real state (runtime path missing)
# ---------------------------------------------------------------------------

class LaneE2GBlockedRuntimeMissingTests(_DbTestBase):
    """Prove BLOCKED in real build because runtime handler does not exist."""

    def test_real_build_returns_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_real_build_runtime_path_exists_false(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertFalse(payload["runtime_path_exists"])

    def test_real_build_e2g_status_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["e2g_status"], E2G_STATUS_BLOCKED)

    def test_blocked_reasons_mention_runtime_handler(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        reasons = payload["first_run_status_reasons"]
        self.assertTrue(
            any("TRACK_FAST_FIRST_15M" in r or "handler" in r.lower() for r in reasons),
            "blocked reasons must mention missing handler",
        )


# ---------------------------------------------------------------------------
# OPERATOR_RUN_READY happy path (patched runtime)
# ---------------------------------------------------------------------------

class LaneE2GReadyPayloadTests(_DbTestBase):
    """Prove OPERATOR_RUN_READY when runtime is patched and all gates pass."""

    def test_ready_with_patched_runtime(self):
        payload = self._ready()
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_READY)

    def test_ready_e2g_status(self):
        self.assertEqual(self._ready()["e2g_status"], E2G_STATUS_READY)

    def test_ready_runtime_path_exists_true(self):
        self.assertTrue(self._ready()["runtime_path_exists"])

    def test_ready_backup_proof_confirmed_true(self):
        self.assertTrue(self._ready()["backup_proof_confirmed"])

    def test_ready_command_name_correct(self):
        self.assertEqual(
            self._ready()["command"],
            "printer-run-e2g-first-bounded-15m-operator-run",
        )

    def test_ready_dry_run_true(self):
        self.assertTrue(self._ready()["dry_run"])

    def test_ready_planning_only_true(self):
        self.assertTrue(self._ready()["planning_only"])

    def test_ready_claude_did_not_run_cycle_true(self):
        self.assertTrue(self._ready()["claude_did_not_run_cycle"])

    def test_ready_reasons_mention_approval_packet(self):
        reasons = self._ready()["first_run_status_reasons"]
        self.assertTrue(any("CYCLE_READY_TO_RUN" in r for r in reasons))

    def test_ready_reasons_mention_backup_proof(self):
        reasons = self._ready()["first_run_status_reasons"]
        self.assertTrue(
            any("backup" in r.lower() for r in reasons),
            "ready reasons must confirm backup proof",
        )

    def test_ready_reasons_mention_operator_must_run(self):
        reasons = self._ready()["first_run_status_reasons"]
        self.assertTrue(any("operator" in r.lower() for r in reasons))

    def test_ready_reasons_mention_not_mean_claude_ran(self):
        reasons = self._ready()["first_run_status_reasons"]
        self.assertTrue(
            any("NOT mean" in r or "did NOT" in r or "did not" in r.lower() for r in reasons),
        )

    def test_ready_reasons_mention_buy_sell_hold_locked(self):
        reasons = self._ready()["first_run_status_reasons"]
        self.assertTrue(
            any("BUY" in r or "SELL" in r or "HOLD" in r for r in reasons),
        )

    def test_ready_e2f_cycle_status_in_packet(self):
        packet = self._ready()["e2f_execution_boundary"]
        self.assertEqual(packet.get("cycle_status"), "CYCLE_READY_TO_RUN")


# ---------------------------------------------------------------------------
# BLOCKED: specific gate failures
# ---------------------------------------------------------------------------

class LaneE2GBlockedGateTests(_DbTestBase):
    """Prove each gate independently blocks."""

    def test_approval_not_confirmed_blocked(self):
        payload = self._blocked(approval_confirmed=False)
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_backup_not_confirmed_blocked(self):
        payload = self._blocked(backup_confirmed=False)
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_backup_proof_none_blocked(self):
        payload = self._blocked(backup_proof_path=None)
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_backup_proof_missing_file_blocked(self):
        payload = self._blocked(backup_proof_path="/no/such/backup.sqlite3")
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_backup_proof_missing_backup_proof_confirmed_false(self):
        payload = self._blocked(backup_proof_path="/no/such/backup.sqlite3")
        self.assertFalse(payload["backup_proof_confirmed"])

    def test_none_token_path_blocked(self):
        payload = self._blocked(token_file_path=None)
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_db_missing_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2g_operator_run_payload(
            tf, "/nonexistent/db.sqlite3",
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_none_db_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2g_operator_run_payload(
            tf, None,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_running_job_blocked(self):
        self._insert_scheduler_job(status="RUNNING")
        payload = self._blocked()
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_locked_at_blocked(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        payload = self._blocked()
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_lock_owner_blocked(self):
        self._insert_scheduler_job(status="PENDING")
        self._set_lock_owner("stale_owner")
        payload = self._blocked()
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_source_budget_exceeded_blocked(self):
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        payload = self._blocked()
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_two_tokens_blocked_e2g_constraint(self):
        """E2G requires exactly 1 token; 2 tokens BLOCKED even if valid."""
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        with patch(_RUNTIME_CHECK_PATCH, return_value=(True, "")):
            payload = build_e2g_operator_run_payload(
                tf, self.db_path,
                approval_confirmed=True,
                backup_confirmed=True,
                backup_proof_path=self.backup_proof_path,
            )
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_two_tokens_blocked_reason_mentions_count(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        with patch(_RUNTIME_CHECK_PATCH, return_value=(True, "")):
            payload = build_e2g_operator_run_payload(
                tf, self.db_path,
                approval_confirmed=True,
                backup_confirmed=True,
                backup_proof_path=self.backup_proof_path,
            )
        reasons = payload["first_run_status_reasons"]
        self.assertTrue(
            any("token_count" in r or "exactly 1" in r for r in reasons),
        )

    def test_zero_tokens_blocked(self):
        tf = self._write_token_file([])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_invalid_mint_blocked(self):
        tf = self._write_token_file([self._valid_entry("not-a-mint")])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_blocked_reasons_nonempty(self):
        payload = self._blocked(token_file_path=None)
        self.assertGreater(len(payload["first_run_status_reasons"]), 0)


# ---------------------------------------------------------------------------
# Payload structure tests
# ---------------------------------------------------------------------------

class LaneE2GPayloadStructureTests(_DbTestBase):
    """Prove all required payload keys are present."""

    def test_has_command(self):
        self.assertIn("command", self._blocked())

    def test_has_dry_run(self):
        self.assertIn("dry_run", self._blocked())

    def test_has_planning_only(self):
        self.assertIn("planning_only", self._blocked())

    def test_has_claude_did_not_run_cycle(self):
        self.assertIn("claude_did_not_run_cycle", self._blocked())

    def test_has_e2f_execution_boundary(self):
        self.assertIn("e2f_execution_boundary", self._blocked())

    def test_has_first_run_status(self):
        self.assertIn("first_run_status", self._blocked())

    def test_has_first_run_status_reasons(self):
        self.assertIn("first_run_status_reasons", self._blocked())

    def test_has_e2g_status(self):
        self.assertIn("e2g_status", self._blocked())

    def test_has_runtime_path_exists(self):
        self.assertIn("runtime_path_exists", self._blocked())

    def test_has_runtime_path_reason(self):
        self.assertIn("runtime_path_reason", self._blocked())

    def test_has_backup_proof_confirmed(self):
        self.assertIn("backup_proof_confirmed", self._blocked())

    def test_has_before_db_counts(self):
        self.assertIn("before_db_counts", self._blocked())

    def test_has_exact_operator_run_command(self):
        self.assertIn("exact_operator_run_command", self._blocked())

    def test_has_allowed_table_deltas(self):
        self.assertIn("allowed_table_deltas", self._blocked())

    def test_has_forbidden_table_deltas(self):
        self.assertIn("forbidden_table_deltas", self._blocked())

    def test_has_stop_conditions(self):
        self.assertIn("stop_conditions", self._blocked())

    def test_has_rollback_checklist(self):
        self.assertIn("rollback_checklist", self._blocked())

    def test_has_hard_locks(self):
        self.assertIn("hard_locks", self._blocked())

    def test_has_next_required_operator_action(self):
        self.assertIn("next_required_operator_action", self._blocked())

    def test_exact_operator_run_command_is_str(self):
        cmd = self._blocked()["exact_operator_run_command"]
        self.assertIsInstance(cmd, str)
        self.assertGreater(len(cmd), 20)

    def test_exact_operator_run_command_mentions_approval_confirmed(self):
        cmd = self._blocked()["exact_operator_run_command"]
        self.assertIn("--approval-confirmed", cmd)

    def test_exact_operator_run_command_mentions_backup_proof_path(self):
        cmd = self._blocked()["exact_operator_run_command"]
        self.assertIn("--backup-proof-path", cmd)

    def test_exact_operator_run_command_mentions_inert(self):
        cmd = self._blocked()["exact_operator_run_command"]
        self.assertTrue(
            "inert" in cmd.lower() or "does NOT execute" in cmd,
            "command must state it is inert text only",
        )

    def test_exact_operator_run_command_mentions_claude_did_not_run(self):
        cmd = self._blocked()["exact_operator_run_command"]
        self.assertTrue(
            "Claude did not" in cmd or "claude did not" in cmd.lower(),
        )

    def test_allowed_table_deltas_is_dict(self):
        self.assertIsInstance(self._blocked()["allowed_table_deltas"], dict)

    def test_allowed_table_deltas_nonempty(self):
        self.assertGreater(len(self._blocked()["allowed_table_deltas"]), 0)

    def test_allowed_table_deltas_mentions_source_requests(self):
        deltas = self._blocked()["allowed_table_deltas"]
        self.assertIn("printer_source_requests", deltas)

    def test_allowed_table_deltas_mentions_memories(self):
        deltas = self._blocked()["allowed_table_deltas"]
        self.assertIn("printer_memories", deltas)

    def test_forbidden_table_deltas_is_list(self):
        self.assertIsInstance(self._blocked()["forbidden_table_deltas"], list)

    def test_forbidden_table_deltas_nonempty(self):
        self.assertGreater(len(self._blocked()["forbidden_table_deltas"]), 0)

    def test_forbidden_table_deltas_mentions_paper_decisions(self):
        forbidden = self._blocked()["forbidden_table_deltas"]
        self.assertTrue(
            any("paper_decision" in f.lower() or "printer_paper_decisions" in f
                for f in forbidden),
        )

    def test_stop_conditions_is_nonempty_list(self):
        items = self._blocked()["stop_conditions"]
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 5)

    def test_stop_conditions_mentions_runtime_handler(self):
        items = self._blocked()["stop_conditions"]
        self.assertTrue(
            any("TRACK_FAST_FIRST_15M" in item or "runtime" in item.lower()
                for item in items),
        )

    def test_stop_conditions_mentions_backup_proof(self):
        items = self._blocked()["stop_conditions"]
        self.assertTrue(
            any("backup proof" in item.lower() for item in items),
        )

    def test_stop_conditions_mentions_buy_sell_hold(self):
        items = self._blocked()["stop_conditions"]
        self.assertTrue(
            any("BUY" in item or "SELL" in item or "HOLD" in item for item in items),
        )

    def test_stop_conditions_mentions_5m_support_only(self):
        items = self._blocked()["stop_conditions"]
        self.assertTrue(
            any("5m" in item for item in items),
            "stop_conditions must mention 5m support-only constraint",
        )

    def test_rollback_checklist_is_nonempty_list(self):
        items = self._blocked()["rollback_checklist"]
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 3)

    def test_rollback_checklist_items_are_checkbox_format(self):
        items = self._blocked()["rollback_checklist"]
        self.assertTrue(all("[ ]" in item for item in items))

    def test_before_db_counts_is_dict_when_db_exists(self):
        self.assertIsInstance(self._blocked()["before_db_counts"], dict)

    def test_before_db_counts_has_source_requests_table(self):
        counts = self._blocked()["before_db_counts"]
        self.assertIn("printer_source_requests", counts)

    def test_before_db_counts_has_scheduler_jobs_table(self):
        counts = self._blocked()["before_db_counts"]
        self.assertIn("printer_scheduler_jobs", counts)

    def test_before_db_counts_has_forbidden_paper_decisions_table(self):
        counts = self._blocked()["before_db_counts"]
        self.assertIn("printer_paper_decisions", counts)

    def test_next_required_operator_action_nonempty(self):
        action = self._blocked()["next_required_operator_action"]
        self.assertIsInstance(action, str)
        self.assertGreater(len(action), 20)

    def test_next_required_operator_action_blocked_mentions_handler(self):
        action = self._blocked()["next_required_operator_action"]
        self.assertTrue(
            "handler" in action.lower() or "TRACK_FAST" in action,
            "blocked action must mention building the handler",
        )

    def test_next_required_operator_action_ready_mentions_commit(self):
        action = self._ready()["next_required_operator_action"]
        self.assertIn("Commit", action)

    def test_payload_json_serializable_blocked(self):
        s = json.dumps(self._blocked())
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 500)

    def test_payload_json_serializable_ready(self):
        s = json.dumps(self._ready())
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 500)

    def test_e2f_execution_boundary_has_cycle_status(self):
        packet = self._blocked()["e2f_execution_boundary"]
        self.assertIn("cycle_status", packet)


# ---------------------------------------------------------------------------
# Hard lock tests
# ---------------------------------------------------------------------------

class LaneE2GHardLockTests(_DbTestBase):
    """Prove all 11 hard-lock flags are False."""

    def test_all_hard_locks_false_in_blocked(self):
        for key, val in self._blocked()["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False even when BLOCKED")

    def test_all_hard_locks_false_in_ready(self):
        for key, val in self._ready()["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False")

    def test_hard_locks_count_is_11(self):
        self.assertEqual(len(self._blocked()["hard_locks"]), 11)

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

    def test_positions_enabled_false(self):
        self.assertIs(HARD_LOCKS["positions_enabled"], False)

    def test_paper_decisions_enabled_false(self):
        self.assertIs(HARD_LOCKS["paper_decisions_enabled"], False)


# ---------------------------------------------------------------------------
# No DB mutation
# ---------------------------------------------------------------------------

class LaneE2GMutationTests(_DbTestBase):
    """Prove no persistent DB mutation during E2G boundary payload build."""

    def test_scheduler_rows_unchanged(self):
        before = self._count_rows("printer_scheduler_jobs")
        self._blocked()
        after = self._count_rows("printer_scheduler_jobs")
        self.assertEqual(before, after)

    def test_source_requests_unchanged(self):
        before = self._count_rows("printer_source_requests")
        self._blocked()
        after = self._count_rows("printer_source_requests")
        self.assertEqual(before, after)

    def test_source_responses_unchanged(self):
        before = self._count_rows("printer_source_responses")
        self._blocked()
        after = self._count_rows("printer_source_responses")
        self.assertEqual(before, after)

    def test_paper_decisions_rows_unchanged(self):
        before = self._count_rows("printer_paper_decisions")
        self._blocked()
        after = self._count_rows("printer_paper_decisions")
        self.assertEqual(before, after)

    def test_e2d_mutation_proof_all_unchanged(self):
        payload = self._blocked()
        proof = (
            payload["e2f_execution_boundary"]
            ["e2e_approval_packet"]
            ["e2d_decision"]
            ["db_mutation_proof"]
        )
        self.assertTrue(proof.get("all_counts_unchanged"))
        self.assertEqual(proof.get("changed_tables", []), [])


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2GCliTests(_DbTestBase):
    """Prove CLI outputs valid JSON and returns 0 for both outcomes."""

    def _run_blocked(self) -> tuple[int, dict]:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        args = [
            "--token-list-path", str(tf),
            "--approval-confirmed",
            "--backup-confirmed",
            "--backup-proof-path", str(self.backup_proof_path),
            "--db-path", str(self.db_path),
            "--format", "json",
        ]
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_run_e2g_first_bounded_15m_operator_run(args)
        return rc, json.loads(captured.getvalue())

    def _run_ready(self) -> tuple[int, dict]:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        args = [
            "--token-list-path", str(tf),
            "--approval-confirmed",
            "--backup-confirmed",
            "--backup-proof-path", str(self.backup_proof_path),
            "--db-path", str(self.db_path),
            "--format", "json",
        ]
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            with patch(_RUNTIME_CHECK_PATCH, return_value=(True, "")):
                rc = main_run_e2g_first_bounded_15m_operator_run(args)
        return rc, json.loads(captured.getvalue())

    def test_cli_returns_0_for_blocked(self):
        rc, _ = self._run_blocked()
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json_blocked(self):
        _, payload = self._run_blocked()
        self.assertIn("first_run_status", payload)

    def test_cli_blocked_status(self):
        _, payload = self._run_blocked()
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_cli_returns_0_for_ready(self):
        rc, _ = self._run_ready()
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json_ready(self):
        _, payload = self._run_ready()
        self.assertIn("first_run_status", payload)

    def test_cli_ready_status(self):
        _, payload = self._run_ready()
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_READY)

    def test_cli_blocked_without_approval_confirmed(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            with patch(_RUNTIME_CHECK_PATCH, return_value=(True, "")):
                rc = main_run_e2g_first_bounded_15m_operator_run([
                    "--token-list-path", str(tf),
                    "--backup-confirmed",
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--db-path", str(self.db_path),
                    "--format", "json",
                ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_cli_blocked_without_backup_confirmed(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            with patch(_RUNTIME_CHECK_PATCH, return_value=(True, "")):
                rc = main_run_e2g_first_bounded_15m_operator_run([
                    "--token-list-path", str(tf),
                    "--approval-confirmed",
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--db-path", str(self.db_path),
                    "--format", "json",
                ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_cli_blocked_without_backup_proof_path(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            with patch(_RUNTIME_CHECK_PATCH, return_value=(True, "")):
                rc = main_run_e2g_first_bounded_15m_operator_run([
                    "--token-list-path", str(tf),
                    "--approval-confirmed",
                    "--backup-confirmed",
                    "--db-path", str(self.db_path),
                    "--format", "json",
                ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_BLOCKED)

    def test_cli_output_has_e2f_execution_boundary(self):
        _, payload = self._run_blocked()
        self.assertIn("e2f_execution_boundary", payload)

    def test_cli_output_has_stop_conditions(self):
        _, payload = self._run_blocked()
        self.assertIn("stop_conditions", payload)

    def test_cli_output_has_rollback_checklist(self):
        _, payload = self._run_blocked()
        self.assertIn("rollback_checklist", payload)

    def test_cli_output_has_before_db_counts(self):
        _, payload = self._run_blocked()
        self.assertIn("before_db_counts", payload)

    def test_cli_ready_output_json_serializable(self):
        _, payload = self._run_ready()
        s = json.dumps(payload)
        self.assertGreater(len(s), 500)


# ---------------------------------------------------------------------------
# Direct source call prevention
# ---------------------------------------------------------------------------

class LaneE2GDirectSourceCallTests(unittest.TestCase):
    """Prove E2G module source does not import real source adapter modules."""

    def _e2g_source(self) -> str:
        path = (SRC_PATH / "printer_v1" / "operator_cli" / "e2g_operator_run.py")
        return path.read_text(encoding="utf-8")

    def test_no_dexscreener_in_e2g_module(self):
        self.assertNotIn("dexscreener", self._e2g_source())

    def test_no_coingecko_in_e2g_module(self):
        self.assertNotIn("coingecko", self._e2g_source())

    def test_no_geckoterminal_in_e2g_module(self):
        self.assertNotIn("geckoterminal", self._e2g_source())

    def test_no_requests_import_in_e2g_module(self):
        self.assertNotIn("import requests", self._e2g_source())

    def test_no_httpx_import_in_e2g_module(self):
        self.assertNotIn("import httpx", self._e2g_source())

    def test_no_real_adapter_calls_in_e2g_module(self):
        src = self._e2g_source()
        self.assertNotIn("execute_source_request", src)
        self.assertNotIn("fetch_real", src)


# ---------------------------------------------------------------------------
# Doc tests
# ---------------------------------------------------------------------------

class LaneE2GDocTests(unittest.TestCase):
    """Prove E2G doc exists with all required statements."""

    def _doc(self) -> str:
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2g-first-bounded-15m-cycle-operator-run.md")
        self.assertTrue(path.exists(), f"E2G doc not found: {path}")
        return path.read_text(encoding="utf-8")

    def test_doc_exists(self):
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2g-first-bounded-15m-cycle-operator-run.md")
        self.assertTrue(path.exists())

    def test_doc_states_claude_did_not_run_cycle(self):
        doc = self._doc()
        self.assertTrue(
            "Claude did not run" in doc or "claude did not run" in doc.lower(),
        )

    def test_doc_states_real_runtime_path_missing(self):
        doc = self._doc()
        self.assertTrue(
            "does NOT exist" in doc or "not implemented" in doc.lower()
            or "not exist" in doc.lower(),
            "doc must state real runtime path does not exist",
        )

    def test_doc_states_does_not_authorize_real_execution(self):
        doc = self._doc()
        self.assertTrue(
            "does NOT authorize" in doc or "does not authorize" in doc.lower(),
        )

    def test_doc_states_operator_must_run_manually(self):
        doc = self._doc()
        self.assertIn("manually", doc.lower())

    def test_doc_mentions_operator_run_ready(self):
        doc = self._doc()
        self.assertIn("OPERATOR_RUN_READY", doc)

    def test_doc_mentions_source_governor_boundary(self):
        doc = self._doc()
        self.assertIn("Source Governor", doc)

    def test_doc_mentions_central_scheduler_boundary(self):
        doc = self._doc()
        self.assertIn("Central Scheduler", doc)

    def test_doc_mentions_track_fast_first_15m(self):
        doc = self._doc()
        self.assertIn("TRACK_FAST_FIRST_15M", doc)

    def test_doc_states_buy_sell_hold_locked(self):
        doc = self._doc()
        self.assertTrue("BUY" in doc and ("SELL" in doc or "HOLD" in doc))

    def test_doc_mentions_stop_conditions(self):
        doc = self._doc()
        self.assertIn("stop condition", doc.lower())

    def test_doc_mentions_rollback(self):
        doc = self._doc()
        self.assertIn("rollback", doc.lower())

    def test_doc_mentions_5m_support_only(self):
        doc = self._doc()
        self.assertIn("5m", doc.lower())

    def test_doc_mentions_zero_memories_valid(self):
        doc = self._doc()
        self.assertTrue(
            "zero" in doc.lower() and "memor" in doc.lower(),
        )

    def test_doc_mentions_hard_locks(self):
        doc = self._doc()
        self.assertIn("hard_lock", doc.lower().replace("-", "_").replace(" ", "_"))

    def test_doc_mentions_before_db_counts(self):
        doc = self._doc()
        self.assertIn("before_db_counts", doc)

    def test_doc_mentions_backup_proof(self):
        doc = self._doc()
        self.assertIn("backup proof", doc.lower())

    def test_doc_mentions_allowed_table_deltas(self):
        doc = self._doc()
        self.assertIn("allowed_table_deltas", doc)

    def test_doc_mentions_forbidden_table_deltas(self):
        doc = self._doc()
        self.assertIn("forbidden", doc.lower())

    def test_doc_mentions_v1_restrictions_remain_active(self):
        doc = self._doc()
        self.assertTrue(
            "remain" in doc.lower() and "active" in doc.lower(),
        )

    def test_doc_states_what_needs_to_be_built(self):
        doc = self._doc()
        self.assertTrue(
            "needs to be built" in doc.lower() or "must be built" in doc.lower()
            or "must be implemented" in doc.lower(),
            "doc must state what needs to be built",
        )


if __name__ == "__main__":
    unittest.main()
