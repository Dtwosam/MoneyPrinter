"""
Post-Lane 10 Lane E2F -- First Bounded 15m Cycle Execution Boundary

Tests prove:
- e2f_execution_boundary module imports cleanly and exports are present
- CYCLE_READY_TO_RUN, CYCLE_BLOCKED, E2F_STATUS_READY, E2F_STATUS_BLOCKED correct
- pyproject.toml entry point registered
- valid 1-token CYCLE_READY_TO_RUN happy path
- valid 2-token CYCLE_READY_TO_RUN happy path
- approval_confirmed=False produces BLOCKED
- E2E blocked (invalid token path) cascades to BLOCKED
- E2E blocked (backup missing) cascades to BLOCKED
- E2E blocked (DB missing) cascades to BLOCKED
- E2E blocked (RUNNING job) cascades to BLOCKED
- E2E blocked (locked_at) cascades to BLOCKED
- E2E blocked (lock_owner) cascades to BLOCKED
- E2E blocked (source budget exceeded) cascades to BLOCKED
- all 11 hard-lock flags false in CYCLE_READY_TO_RUN payload
- all 11 hard-lock flags false in BLOCKED payload
- hard_locks count is 11
- e2e_approval_packet included in payload
- cycle_status is CYCLE_READY_TO_RUN or BLOCKED
- cycle_status_reasons is nonempty list
- e2f_status is correct string
- exact_operator_run_command is a non-empty string (inert text only)
- exact_operator_run_command does not execute anything
- exact_operator_run_command mentions approval-confirmed flag
- mutation_plan is a dict with required keys
- mutation_plan forbidden_table_deltas includes paper decisions
- stop_conditions is a nonempty list
- rollback_checklist is a nonempty list
- planning_only true
- claude_did_not_run_cycle true
- dry_run true
- no DB mutation (row counts unchanged)
- payload is JSON-serializable for CYCLE_READY_TO_RUN
- payload is JSON-serializable for BLOCKED
- CLI outputs valid JSON for READY
- CLI outputs valid JSON for BLOCKED
- CLI --approval-confirmed flag required for READY
- CLI blocked without --approval-confirmed
- BLOCKED returns exit code 0
- READY returns exit code 0
- no source-fetching libraries imported
- command name correct
- next_required_operator_action present and nonempty
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
from printer_v1.operator_cli.commands import main_run_first_bounded_15m_cycle
from printer_v1.operator_cli.e2f_execution_boundary import (
    CYCLE_BLOCKED,
    CYCLE_READY_TO_RUN,
    E2F_STATUS_BLOCKED,
    E2F_STATUS_READY,
    build_e2f_execution_boundary_payload,
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

_VALID_NOTE = "Operator-approved for E2F test. Reviewed 2026-06-27."


class _DbTestBase(unittest.TestCase):
    """Temp SQLite DB with migrations plus temp dir for token files."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2f_test.sqlite3"
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
                ("e2f_test_job", "TRACK_FAST_FIRST_15M", status, "2026-06-27T12:00:00"),
            )
            if locked_at is not None:
                conn.execute(
                    "UPDATE printer_scheduler_jobs SET locked_at = ?"
                    " WHERE job_name = 'e2f_test_job'",
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
                " WHERE job_name = 'e2f_test_job'",
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

class LaneE2FImportTests(unittest.TestCase):
    """Prove module imports cleanly and constants are correct."""

    def test_module_importable(self):
        import printer_v1.operator_cli.e2f_execution_boundary as mod
        self.assertIsNotNone(mod)

    def test_cycle_ready_to_run_value(self):
        self.assertEqual(CYCLE_READY_TO_RUN, "CYCLE_READY_TO_RUN")

    def test_cycle_blocked_value(self):
        self.assertEqual(CYCLE_BLOCKED, "BLOCKED")

    def test_e2f_status_ready_value(self):
        self.assertEqual(E2F_STATUS_READY, "E2F_EXECUTION_BOUNDARY_READY")

    def test_e2f_status_blocked_value(self):
        self.assertEqual(E2F_STATUS_BLOCKED, "E2F_EXECUTION_BOUNDARY_BLOCKED")

    def test_cli_command_importable(self):
        self.assertTrue(callable(main_run_first_bounded_15m_cycle))

    def test_no_http_libraries_imported(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(lib, sys.modules,
                f"Network library {lib!r} must not be imported")

    def test_pyproject_entry_point_registered(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-run-first-bounded-15m-cycle", content)
        self.assertIn("main_run_first_bounded_15m_cycle", content)


# ---------------------------------------------------------------------------
# CYCLE_READY_TO_RUN happy path
# ---------------------------------------------------------------------------

class LaneE2FReadyPayloadTests(_DbTestBase):
    """Prove CYCLE_READY_TO_RUN for valid inputs with approval confirmed."""

    def _ready_1(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1, "TRACK_FAST")])
        return build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )

    def _ready_2(self) -> dict:
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        return build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )

    def test_single_token_produces_ready(self):
        self.assertEqual(self._ready_1()["cycle_status"], CYCLE_READY_TO_RUN)

    def test_two_token_produces_ready(self):
        self.assertEqual(self._ready_2()["cycle_status"], CYCLE_READY_TO_RUN)

    def test_e2f_status_ready_when_ready(self):
        self.assertEqual(self._ready_1()["e2f_status"], E2F_STATUS_READY)

    def test_command_name_correct(self):
        self.assertEqual(
            self._ready_1()["command"],
            "printer-run-first-bounded-15m-cycle",
        )

    def test_dry_run_true(self):
        self.assertTrue(self._ready_1()["dry_run"])

    def test_planning_only_true(self):
        self.assertTrue(self._ready_1()["planning_only"])

    def test_claude_did_not_run_cycle_true(self):
        self.assertTrue(self._ready_1()["claude_did_not_run_cycle"])

    def test_ready_reasons_mention_approval_packet_ready(self):
        reasons = self._ready_1()["cycle_status_reasons"]
        self.assertTrue(any("APPROVAL_PACKET_READY" in r for r in reasons))

    def test_ready_reasons_mention_approval_confirmed(self):
        reasons = self._ready_1()["cycle_status_reasons"]
        self.assertTrue(any("approval_confirmed" in r for r in reasons))

    def test_ready_reasons_mention_operator_must_run(self):
        reasons = self._ready_1()["cycle_status_reasons"]
        self.assertTrue(any("operator" in r.lower() for r in reasons))

    def test_ready_reasons_mention_not_mean_claude_ran(self):
        reasons = self._ready_1()["cycle_status_reasons"]
        self.assertTrue(
            any("NOT mean" in r or "did NOT" in r or "did not" in r.lower() for r in reasons),
            "reasons must state CYCLE_READY_TO_RUN does not mean Claude ran the cycle",
        )

    def test_ready_reasons_mention_buy_sell_hold_locked(self):
        reasons = self._ready_1()["cycle_status_reasons"]
        self.assertTrue(
            any("BUY" in r or "SELL" in r or "HOLD" in r for r in reasons),
            "reasons must state BUY/SELL/HOLD remain locked",
        )

    def test_ready_e2e_packet_contains_approval_packet_ready(self):
        packet = self._ready_1()["e2e_approval_packet"]
        self.assertEqual(packet.get("approval_packet_status"), "APPROVAL_PACKET_READY")


# ---------------------------------------------------------------------------
# BLOCKED cases
# ---------------------------------------------------------------------------

class LaneE2FBlockedApprovalNotConfirmedTests(_DbTestBase):
    """Prove BLOCKED when approval_confirmed is False."""

    def test_approval_not_confirmed_blocks(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=False,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_approval_not_confirmed_blocked_reasons_mention_approval_confirmed(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=False,
            backup_confirmed=True,
        )
        reasons = payload["cycle_status_reasons"]
        self.assertTrue(any("approval_confirmed" in r for r in reasons))

    def test_approval_not_confirmed_e2f_status_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=False,
            backup_confirmed=True,
        )
        self.assertEqual(payload["e2f_status"], E2F_STATUS_BLOCKED)


class LaneE2FBlockedCascadeTests(_DbTestBase):
    """Prove BLOCKED when E2E approval packet is blocked (cascades)."""

    def test_none_token_path_blocked(self):
        payload = build_e2f_execution_boundary_payload(
            None, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_missing_file_blocked(self):
        payload = build_e2f_execution_boundary_payload(
            "/no/such/tokens.json", self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_backup_not_confirmed_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=False,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_db_missing_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, "/nonexistent/db.sqlite3",
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_none_db_blocked(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, None,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_running_job_blocked(self):
        self._insert_scheduler_job(status="RUNNING")
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_locked_at_blocked(self):
        self._insert_scheduler_job(status="PENDING", locked_at="2026-06-27T12:00:00")
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_lock_owner_blocked(self):
        self._insert_scheduler_job(status="PENDING")
        self._set_lock_owner("stale_owner")
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_source_budget_exceeded_blocked(self):
        for _ in range(_RATE_LIMIT):
            self._record_success_attempt(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND)
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_zero_tokens_blocked(self):
        tf = self._write_token_file([])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_invalid_mint_blocked(self):
        tf = self._write_token_file([self._valid_entry("not-a-mint")])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_blocked_reasons_nonempty(self):
        payload = build_e2f_execution_boundary_payload(
            None, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertGreater(len(payload["cycle_status_reasons"]), 0)

    def test_blocked_e2e_approval_packet_still_present(self):
        payload = build_e2f_execution_boundary_payload(
            None, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertIn("e2e_approval_packet", payload)
        self.assertEqual(payload["e2e_approval_packet"]["approval_packet_status"], "BLOCKED")

    def test_both_blocked_approval_and_cascade(self):
        """BLOCKED if both approval_confirmed=False AND E2E is blocked."""
        payload = build_e2f_execution_boundary_payload(
            None, self.db_path,
            approval_confirmed=False,
            backup_confirmed=True,
        )
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)
        reasons = payload["cycle_status_reasons"]
        self.assertGreater(len(reasons), 1)


# ---------------------------------------------------------------------------
# Payload structure
# ---------------------------------------------------------------------------

class LaneE2FPayloadStructureTests(_DbTestBase):
    """Prove all required payload keys are present."""

    def _ready(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        return build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )

    def _blocked(self) -> dict:
        return build_e2f_execution_boundary_payload(
            None, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )

    def _blocked_no_approval(self) -> dict:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        return build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=False,
            backup_confirmed=True,
        )

    def test_has_command(self):
        self.assertIn("command", self._ready())

    def test_has_dry_run(self):
        self.assertIn("dry_run", self._ready())

    def test_has_planning_only(self):
        self.assertIn("planning_only", self._ready())

    def test_has_claude_did_not_run_cycle(self):
        self.assertIn("claude_did_not_run_cycle", self._ready())

    def test_has_e2e_approval_packet(self):
        self.assertIn("e2e_approval_packet", self._ready())

    def test_has_cycle_status(self):
        self.assertIn("cycle_status", self._ready())

    def test_has_cycle_status_reasons(self):
        self.assertIn("cycle_status_reasons", self._ready())

    def test_has_e2f_status(self):
        self.assertIn("e2f_status", self._ready())

    def test_has_exact_operator_run_command(self):
        self.assertIn("exact_operator_run_command", self._ready())

    def test_has_mutation_plan(self):
        self.assertIn("mutation_plan", self._ready())

    def test_has_stop_conditions(self):
        self.assertIn("stop_conditions", self._ready())

    def test_has_rollback_checklist(self):
        self.assertIn("rollback_checklist", self._ready())

    def test_has_hard_locks(self):
        self.assertIn("hard_locks", self._ready())

    def test_has_next_required_operator_action(self):
        self.assertIn("next_required_operator_action", self._ready())

    def test_exact_operator_run_command_is_str(self):
        cmd = self._ready()["exact_operator_run_command"]
        self.assertIsInstance(cmd, str)
        self.assertGreater(len(cmd), 10)

    def test_exact_operator_run_command_mentions_approval_confirmed(self):
        cmd = self._ready()["exact_operator_run_command"]
        self.assertIn("--approval-confirmed", cmd)

    def test_exact_operator_run_command_mentions_inert_or_not_execute(self):
        cmd = self._ready()["exact_operator_run_command"]
        self.assertTrue(
            "inert" in cmd.lower() or "does NOT execute" in cmd or "not execute" in cmd.lower(),
            "exact_operator_run_command must state it is inert text only",
        )

    def test_exact_operator_run_command_mentions_claude_did_not_run(self):
        cmd = self._ready()["exact_operator_run_command"]
        self.assertTrue(
            "Claude did not" in cmd or "claude did not" in cmd.lower(),
            "exact_operator_run_command must state Claude did not run it",
        )

    def test_exact_operator_run_command_present_in_blocked(self):
        payload = self._blocked()
        self.assertIn("exact_operator_run_command", payload)
        self.assertIsInstance(payload["exact_operator_run_command"], str)

    def test_mutation_plan_is_dict(self):
        mp = self._ready()["mutation_plan"]
        self.assertIsInstance(mp, dict)

    def test_mutation_plan_has_allowed_table_deltas(self):
        mp = self._ready()["mutation_plan"]
        self.assertIn("allowed_table_deltas", mp)
        self.assertIsInstance(mp["allowed_table_deltas"], dict)
        self.assertGreater(len(mp["allowed_table_deltas"]), 0)

    def test_mutation_plan_has_forbidden_table_deltas(self):
        mp = self._ready()["mutation_plan"]
        self.assertIn("forbidden_table_deltas", mp)
        forbidden = mp["forbidden_table_deltas"]
        self.assertIsInstance(forbidden, list)
        self.assertGreater(len(forbidden), 0)

    def test_mutation_plan_forbidden_mentions_paper_decisions(self):
        forbidden = self._ready()["mutation_plan"]["forbidden_table_deltas"]
        self.assertTrue(
            any("paper_decision" in f.lower() or "printer_paper_decisions" in f for f in forbidden),
            "forbidden_table_deltas must include paper decisions",
        )

    def test_mutation_plan_paper_decisions_enabled_false(self):
        mp = self._ready()["mutation_plan"]
        self.assertIs(mp.get("paper_decisions_enabled"), False)

    def test_mutation_plan_buy_sell_hold_enabled_false(self):
        mp = self._ready()["mutation_plan"]
        self.assertIs(mp.get("buy_sell_hold_enabled"), False)

    def test_mutation_plan_positions_enabled_false(self):
        mp = self._ready()["mutation_plan"]
        self.assertIs(mp.get("positions_enabled"), False)

    def test_mutation_plan_zero_memories_valid(self):
        mp = self._ready()["mutation_plan"]
        self.assertTrue(mp.get("zero_clean_memories_is_valid"))

    def test_stop_conditions_is_nonempty_list(self):
        items = self._ready()["stop_conditions"]
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 5)

    def test_stop_conditions_mentions_approval_confirmed(self):
        items = self._ready()["stop_conditions"]
        self.assertTrue(
            any("approval_confirmed" in item for item in items),
            "stop_conditions must mention approval_confirmed",
        )

    def test_stop_conditions_mentions_buy_sell_hold(self):
        items = self._ready()["stop_conditions"]
        self.assertTrue(
            any("BUY" in item or "SELL" in item or "HOLD" in item for item in items),
        )

    def test_rollback_checklist_is_nonempty_list(self):
        items = self._ready()["rollback_checklist"]
        self.assertIsInstance(items, list)
        self.assertGreater(len(items), 3)

    def test_rollback_checklist_items_start_with_bracket(self):
        items = self._ready()["rollback_checklist"]
        self.assertTrue(
            all("[ ]" in item or item.startswith("[") for item in items),
            "rollback checklist items should be checkbox format",
        )

    def test_next_required_operator_action_nonempty_str(self):
        action = self._ready()["next_required_operator_action"]
        self.assertIsInstance(action, str)
        self.assertGreater(len(action), 20)

    def test_next_required_operator_action_mentions_commit(self):
        action = self._ready()["next_required_operator_action"]
        self.assertIn("Commit", action)

    def test_next_required_operator_action_blocked_mentions_resolve(self):
        action = self._blocked_no_approval()["next_required_operator_action"]
        self.assertTrue(
            "Resolve" in action or "resolve" in action.lower(),
            "blocked action must mention resolving blocked reasons",
        )

    def test_payload_json_serializable_ready(self):
        s = json.dumps(self._ready())
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 500)

    def test_payload_json_serializable_blocked(self):
        s = json.dumps(self._blocked())
        self.assertIsInstance(s, str)

    def test_cycle_status_reasons_nonempty_for_ready(self):
        reasons = self._ready()["cycle_status_reasons"]
        self.assertIsInstance(reasons, list)
        self.assertGreater(len(reasons), 0)

    def test_e2e_approval_packet_has_e2d_decision(self):
        packet = self._ready()["e2e_approval_packet"]
        self.assertIn("e2d_decision", packet)

    def test_e2e_approval_packet_e2d_final_decision_go(self):
        packet = self._ready()["e2e_approval_packet"]
        self.assertEqual(
            packet["e2d_decision"]["final_decision"],
            "GO_TO_OPERATOR_APPROVAL",
        )


# ---------------------------------------------------------------------------
# Hard lock tests
# ---------------------------------------------------------------------------

class LaneE2FHardLockTests(_DbTestBase):
    """Prove all 11 hard-lock flags are False."""

    def test_all_hard_locks_false_in_ready(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False")

    def test_hard_locks_count_is_11(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        self.assertEqual(len(payload["hard_locks"]), 11)

    def test_all_hard_locks_false_in_blocked(self):
        payload = build_e2f_execution_boundary_payload(
            None, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
        )
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False even when BLOCKED")

    def test_all_hard_locks_false_when_approval_not_confirmed(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path,
            approval_confirmed=False,
            backup_confirmed=True,
        )
        for key, val in payload["hard_locks"].items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False even when approval not confirmed")

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

    def test_paper_decisions_enabled_false(self):
        self.assertIs(HARD_LOCKS["paper_decisions_enabled"], False)

    def test_positions_enabled_false(self):
        self.assertIs(HARD_LOCKS["positions_enabled"], False)


# ---------------------------------------------------------------------------
# No DB mutation
# ---------------------------------------------------------------------------

class LaneE2FMutationTests(_DbTestBase):
    """Prove no persistent DB mutation during boundary payload build."""

    def test_scheduler_rows_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_scheduler_jobs")
        build_e2f_execution_boundary_payload(
            tf, self.db_path, approval_confirmed=True, backup_confirmed=True
        )
        after = self._count_rows("printer_scheduler_jobs")
        self.assertEqual(before, after)

    def test_source_requests_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_requests")
        build_e2f_execution_boundary_payload(
            tf, self.db_path, approval_confirmed=True, backup_confirmed=True
        )
        after = self._count_rows("printer_source_requests")
        self.assertEqual(before, after)

    def test_source_responses_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        before = self._count_rows("printer_source_responses")
        build_e2f_execution_boundary_payload(
            tf, self.db_path, approval_confirmed=True, backup_confirmed=True
        )
        after = self._count_rows("printer_source_responses")
        self.assertEqual(before, after)

    def test_e2d_mutation_proof_all_unchanged(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        payload = build_e2f_execution_boundary_payload(
            tf, self.db_path, approval_confirmed=True, backup_confirmed=True
        )
        proof = payload["e2e_approval_packet"]["e2d_decision"]["db_mutation_proof"]
        self.assertTrue(proof.get("all_counts_unchanged"))
        self.assertEqual(proof.get("changed_tables", []), [])


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2FCliTests(_DbTestBase):
    """Prove CLI outputs valid JSON and returns 0 for both READY and BLOCKED."""

    def _run_ready(self) -> tuple[int, dict]:
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        args = [
            "--token-list-path", str(tf),
            "--approval-confirmed",
            "--backup-confirmed",
            "--db-path", str(self.db_path),
            "--format", "json",
        ]
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_run_first_bounded_15m_cycle(args)
        return rc, json.loads(captured.getvalue())

    def test_cli_returns_0_for_ready(self):
        rc, _ = self._run_ready()
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json_ready(self):
        _, payload = self._run_ready()
        self.assertIn("cycle_status", payload)

    def test_cli_ready_status(self):
        _, payload = self._run_ready()
        self.assertEqual(payload["cycle_status"], CYCLE_READY_TO_RUN)

    def test_cli_returns_0_for_blocked(self):
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_run_first_bounded_15m_cycle([
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_cli_blocked_without_approval_confirmed(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_run_first_bounded_15m_cycle([
                "--token-list-path", str(tf),
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_cli_blocked_without_backup_confirmed(self):
        tf = self._write_token_file([self._valid_entry(_MINT_1)])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_run_first_bounded_15m_cycle([
                "--token-list-path", str(tf),
                "--approval-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_cli_two_tokens_ready(self):
        tf = self._write_token_file([
            self._valid_entry(_MINT_1, "TRACK_FAST"),
            self._valid_entry(_MINT_2, "TRACK_NORMAL"),
        ])
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            main_run_first_bounded_15m_cycle([
                "--token-list-path", str(tf),
                "--approval-confirmed",
                "--backup-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["cycle_status"], CYCLE_READY_TO_RUN)

    def test_cli_output_has_e2e_approval_packet(self):
        _, payload = self._run_ready()
        self.assertIn("e2e_approval_packet", payload)

    def test_cli_output_has_exact_operator_run_command(self):
        _, payload = self._run_ready()
        self.assertIn("exact_operator_run_command", payload)

    def test_cli_output_has_mutation_plan(self):
        _, payload = self._run_ready()
        self.assertIn("mutation_plan", payload)

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
            rc = main_run_first_bounded_15m_cycle([
                "--token-list-path", str(tf),
                "--approval-confirmed",
                "--db-path", str(self.db_path),
                "--format", "json",
            ])
        self.assertEqual(rc, 0)
        payload = json.loads(captured.getvalue())
        self.assertEqual(payload["cycle_status"], CYCLE_BLOCKED)

    def test_cli_ready_output_json_serializable(self):
        _, payload = self._run_ready()
        s = json.dumps(payload)
        self.assertGreater(len(s), 500)


# ---------------------------------------------------------------------------
# Execution boundary doc tests
# ---------------------------------------------------------------------------

class LaneE2FDocTests(unittest.TestCase):
    """Prove execution boundary doc exists with required statements."""

    def _doc(self) -> str:
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2f-first-bounded-15m-cycle-execution-boundary.md")
        self.assertTrue(path.exists(), f"E2F doc not found: {path}")
        return path.read_text(encoding="utf-8")

    def test_doc_exists(self):
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2f-first-bounded-15m-cycle-execution-boundary.md")
        self.assertTrue(path.exists())

    def test_doc_states_claude_did_not_run_cycle(self):
        doc = self._doc()
        self.assertTrue(
            "Claude did not run" in doc or "claude did not run" in doc.lower(),
            "doc must state Claude did not run the cycle",
        )

    def test_doc_states_does_not_authorize_real_execution(self):
        doc = self._doc()
        self.assertTrue(
            "does NOT authorize" in doc or "does not authorize" in doc.lower(),
            "doc must state E2F does NOT authorize real execution by itself",
        )

    def test_doc_states_operator_must_run_manually(self):
        doc = self._doc()
        self.assertTrue(
            "manually" in doc.lower(),
            "doc must state operator must run command manually",
        )

    def test_doc_mentions_cycle_ready_to_run(self):
        doc = self._doc()
        self.assertIn("CYCLE_READY_TO_RUN", doc)

    def test_doc_mentions_source_governor_boundary(self):
        doc = self._doc()
        self.assertTrue(
            "Source Governor" in doc or "source governor" in doc.lower(),
            "doc must mention Source Governor execution boundary",
        )

    def test_doc_mentions_central_scheduler_boundary(self):
        doc = self._doc()
        self.assertTrue(
            "Central Scheduler" in doc or "central scheduler" in doc.lower(),
            "doc must mention Central Scheduler boundary",
        )

    def test_doc_mentions_mutation_plan(self):
        doc = self._doc()
        self.assertTrue(
            "mutation" in doc.lower(),
            "doc must mention mutation plan",
        )

    def test_doc_states_buy_sell_hold_locked(self):
        doc = self._doc()
        self.assertTrue(
            "BUY" in doc and ("SELL" in doc or "HOLD" in doc),
            "doc must state BUY/SELL/HOLD remain locked",
        )

    def test_doc_mentions_stop_conditions(self):
        doc = self._doc()
        self.assertIn("stop condition", doc.lower())

    def test_doc_mentions_rollback(self):
        doc = self._doc()
        self.assertIn("rollback", doc.lower())

    def test_doc_states_all_v1_restrictions_remain_active(self):
        doc = self._doc()
        self.assertTrue(
            "remain" in doc.lower() and "active" in doc.lower(),
            "doc must state all V1 restrictions remain active",
        )

    def test_doc_mentions_e2e(self):
        doc = self._doc()
        self.assertIn("E2E", doc)

    def test_doc_mentions_hard_locks(self):
        doc = self._doc()
        self.assertIn("hard_lock", doc.lower().replace("-", "_").replace(" ", "_"))

    def test_doc_mentions_exact_operator_run_command(self):
        doc = self._doc()
        self.assertIn("exact_operator_run_command", doc)

    def test_doc_mentions_5m_support_only(self):
        doc = self._doc()
        self.assertIn("5m", doc.lower())

    def test_doc_mentions_zero_memories_valid(self):
        doc = self._doc()
        self.assertTrue(
            "zero" in doc.lower() and "memor" in doc.lower(),
            "doc must mention zero memories is a valid outcome",
        )


if __name__ == "__main__":
    unittest.main()
