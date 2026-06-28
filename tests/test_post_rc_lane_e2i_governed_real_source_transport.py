"""
Post-Lane 10 Lane E2I -- Governed Real Source Transport Boundary

Tests prove:
- e2i_source_transport module imports cleanly
- E2I_TRANSPORT_SOURCE_NAME is "dexscreener"
- E2I_TRANSPORT_REQUEST_KIND is "pair_market_snapshot"
- E2I_STATUS_EXECUTED and E2I_STATUS_BLOCKED defined
- check_real_source_transport_available() returns (True, reason)
- reason mentions E2I or DexScreener or real transport
- is_real_source_transport_available() returns True
- build_e2i_dexscreener_adapter() returns enabled adapter
- build_e2i_dexscreener_adapter() has smoke transport
- execute_e2i_governed_smoke: with fixture adapter writes source request row
- execute_e2i_governed_smoke: with fixture adapter writes source response row
- execute_e2i_governed_smoke: returns GovernedSourceExecutionResult
- execute_e2i_governed_smoke: records governor allowed when fixture succeeds
- build_e2i_one_shot_smoke_payload: blocked when operator_approved=False
- build_e2i_one_shot_smoke_payload: blocked when backup_proof_path missing
- build_e2i_one_shot_smoke_payload: blocked when db_path missing
- build_e2i_one_shot_smoke_payload: blocked when token list missing
- build_e2i_one_shot_smoke_payload: blocked when token list has no TRACK_FAST token
- build_e2i_one_shot_smoke_payload: executed with fixture adapter + all gates pass
- build_e2i_one_shot_smoke_payload: executed status is E2I_STATUS_EXECUTED
- build_e2i_one_shot_smoke_payload: has before_counts dict
- build_e2i_one_shot_smoke_payload: has after_counts dict
- build_e2i_one_shot_smoke_payload: before_counts has source_requests table
- build_e2i_one_shot_smoke_payload: after_counts source_requests > before after execution
- build_e2i_one_shot_smoke_payload: paper_decisions_created is 0
- build_e2i_one_shot_smoke_payload: positions_created is 0
- build_e2i_one_shot_smoke_payload: pnl_created is 0
- build_e2i_one_shot_smoke_payload: snapshots_created is 0
- build_e2i_one_shot_smoke_payload: memories_created is 0
- build_e2i_one_shot_smoke_payload: claude_did_not_run_cycle is True
- build_e2i_one_shot_smoke_payload: hard_locks all True
- build_e2i_one_shot_smoke_payload: no paper rows written to DB
- build_e2i_one_shot_smoke_payload: no snapshot rows written to DB
- build_e2i_one_shot_smoke_payload: no memory rows written to DB
- CLI: main_run_e2i_one_shot_governed_source_smoke exists and is callable
- CLI: returns 0 for valid args with fixture adapter
- CLI: outputs valid JSON
- CLI: payload has command field
- CLI: blocked when --operator-approved not set
- E2H integration: E2H check_real_source_transport_available() returns True via E2I
- E2G integration: E2G reports OPERATOR_RUN_READY after E2I (all gates pass)
- pyproject.toml entry registered
- doc exists with required statements
- doc states token-specific transport (no generic search)
- forbidden tables remain zero when smoke executed
- _FORBIDDEN_SMOKE_TABLES is defined and non-empty
- _AUDIT_TABLES is defined and non-empty
- no buy/sell/hold hard lock flags can be set to True
- _GENERIC_SEARCH_FORBIDDEN constant is True
- E2I module source has no q=SOL generic search URL
- build_e2i_dexscreener_adapter() raises TypeError when token_mint omitted
- build_e2i_dexscreener_adapter() raises ValueError for empty/placeholder token_mint
- executed payload has approved_token_mint matching token list mint
- smoke_target includes the approved token mint
- smoke_target does not contain q=SOL
- generic_search_used is False in both EXECUTED and BLOCKED states
- blocked payload has approved_token_mint=None
- more than 1 TRACK_FAST token remains blocked
- no broad discovery in one-shot smoke
- DEXSCREENER_TOKEN_URL_TEMPLATE exists and contains {token_mint} not q=SOL
- build_dexscreener_token_transport exists and returns callable
- hard_locks includes no_generic_search: True
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

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.e2i_source_transport import (
    E2I_TRANSPORT_SOURCE_NAME,
    E2I_TRANSPORT_REQUEST_KIND,
    E2I_STATUS_EXECUTED,
    E2I_STATUS_BLOCKED,
    _FORBIDDEN_SMOKE_TABLES,
    _AUDIT_TABLES,
    _GENERIC_SEARCH_FORBIDDEN,
    check_real_source_transport_available,
    is_real_source_transport_available,
    build_e2i_dexscreener_adapter,
    build_e2i_one_shot_smoke_payload,
    execute_e2i_governed_smoke,
)
from printer_v1.operator_cli.commands import main_run_e2i_one_shot_governed_source_smoke
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    FIXTURE_SUCCESS,
)


_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_VALID_NOTE = "Operator-approved for E2I test. Reviewed 2026-06-28."


def _build_fixture_adapter():
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_kind=FIXTURE_SUCCESS,
        fixture_payload={"pairs": [{"chainId": "solana", "pairAddress": "test123"}]},
    )


class _DbTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
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

    def _write_token_file(self, tokens: list[dict]) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")
        return tf

    def _valid_token_entry(self, mint: str = _MINT_1) -> dict:
        return {
            "token_mint": mint,
            "lifecycle_lane": "TRACK_FAST",
            "approved_by_operator": True,
            "operator_note": _VALID_NOTE,
        }


# ---------------------------------------------------------------------------
# Module and constant tests
# ---------------------------------------------------------------------------

class LaneE2IImportTests(unittest.TestCase):
    def test_module_importable(self):
        import printer_v1.operator_cli.e2i_source_transport as mod
        self.assertIsNotNone(mod)

    def test_transport_source_name_is_dexscreener(self):
        self.assertEqual(E2I_TRANSPORT_SOURCE_NAME, "dexscreener")

    def test_transport_request_kind_is_pair_market_snapshot(self):
        self.assertEqual(E2I_TRANSPORT_REQUEST_KIND, "pair_market_snapshot")

    def test_status_executed_defined(self):
        self.assertIsInstance(E2I_STATUS_EXECUTED, str)
        self.assertGreater(len(E2I_STATUS_EXECUTED), 5)

    def test_status_blocked_defined(self):
        self.assertIsInstance(E2I_STATUS_BLOCKED, str)
        self.assertGreater(len(E2I_STATUS_BLOCKED), 5)

    def test_forbidden_tables_nonempty(self):
        self.assertGreater(len(_FORBIDDEN_SMOKE_TABLES), 0)

    def test_forbidden_tables_includes_paper_decisions(self):
        self.assertIn("printer_paper_decisions", _FORBIDDEN_SMOKE_TABLES)

    def test_forbidden_tables_includes_token_snapshots(self):
        self.assertIn("printer_token_snapshots", _FORBIDDEN_SMOKE_TABLES)

    def test_forbidden_tables_includes_memories(self):
        self.assertIn("printer_memories", _FORBIDDEN_SMOKE_TABLES)

    def test_audit_tables_nonempty(self):
        self.assertGreater(len(_AUDIT_TABLES), 0)

    def test_audit_tables_includes_source_requests(self):
        self.assertIn("printer_source_requests", _AUDIT_TABLES)

    def test_audit_tables_includes_source_responses(self):
        self.assertIn("printer_source_responses", _AUDIT_TABLES)

    def test_cli_command_importable(self):
        self.assertTrue(callable(main_run_e2i_one_shot_governed_source_smoke))

    def test_pyproject_entry_registered(self):
        content = (PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        self.assertIn("printer-run-e2i-one-shot-governed-source-smoke", content)
        self.assertIn("main_run_e2i_one_shot_governed_source_smoke", content)


# ---------------------------------------------------------------------------
# Transport availability
# ---------------------------------------------------------------------------

class LaneE2ITransportAvailabilityTests(unittest.TestCase):
    def test_check_returns_true(self):
        ok, _ = check_real_source_transport_available()
        self.assertTrue(ok)

    def test_check_reason_mentions_e2i_or_dexscreener(self):
        _, reason = check_real_source_transport_available()
        self.assertTrue(
            "e2i" in reason.lower() or "dexscreener" in reason.lower(),
        )

    def test_check_reason_mentions_smoke_or_transport(self):
        _, reason = check_real_source_transport_available()
        self.assertTrue(
            "smoke" in reason.lower() or "transport" in reason.lower(),
        )

    def test_check_reason_mentions_available_or_real(self):
        _, reason = check_real_source_transport_available()
        self.assertTrue(
            "available" in reason.lower() or "real" in reason.lower(),
        )

    def test_is_real_transport_available_true(self):
        self.assertTrue(is_real_source_transport_available())


# ---------------------------------------------------------------------------
# Adapter construction (no network calls)
# ---------------------------------------------------------------------------

class LaneE2IAdapterBuildTests(unittest.TestCase):
    def test_build_adapter_returns_adapter(self):
        from printer_v1.sources.dexscreener import DexScreenerAdapter
        adapter = build_e2i_dexscreener_adapter(token_mint=_MINT_1)
        self.assertIsInstance(adapter, DexScreenerAdapter)

    def test_build_adapter_is_enabled(self):
        adapter = build_e2i_dexscreener_adapter(token_mint=_MINT_1)
        self.assertTrue(adapter.enabled)

    def test_build_adapter_has_transport(self):
        adapter = build_e2i_dexscreener_adapter(token_mint=_MINT_1)
        self.assertIsNotNone(adapter.transport)

    def test_build_adapter_call_count_starts_zero(self):
        adapter = build_e2i_dexscreener_adapter(token_mint=_MINT_1)
        self.assertEqual(adapter.call_count, 0)


# ---------------------------------------------------------------------------
# Governed smoke execution (fixture adapter, no network)
# ---------------------------------------------------------------------------

class LaneE2IGovernedSmokeTests(_DbTestBase):
    def test_smoke_returns_result(self):
        from printer_v1.sources.governed_execution import GovernedSourceExecutionResult
        adapter = _build_fixture_adapter()
        result = execute_e2i_governed_smoke(str(self.db_path), adapter=adapter)
        self.assertIsInstance(result, GovernedSourceExecutionResult)

    def test_smoke_writes_source_request_row(self):
        before = self._count_rows("printer_source_requests")
        execute_e2i_governed_smoke(str(self.db_path), adapter=_build_fixture_adapter())
        self.assertGreater(self._count_rows("printer_source_requests"), before)

    def test_smoke_writes_source_response_row(self):
        before = self._count_rows("printer_source_responses")
        execute_e2i_governed_smoke(str(self.db_path), adapter=_build_fixture_adapter())
        self.assertGreater(self._count_rows("printer_source_responses"), before)

    def test_smoke_does_not_write_paper_decisions(self):
        before = self._count_rows("printer_paper_decisions")
        execute_e2i_governed_smoke(str(self.db_path), adapter=_build_fixture_adapter())
        self.assertEqual(self._count_rows("printer_paper_decisions"), before)

    def test_smoke_does_not_write_token_snapshots(self):
        before = self._count_rows("printer_token_snapshots")
        execute_e2i_governed_smoke(str(self.db_path), adapter=_build_fixture_adapter())
        self.assertEqual(self._count_rows("printer_token_snapshots"), before)

    def test_smoke_request_record_not_none(self):
        result = execute_e2i_governed_smoke(str(self.db_path), adapter=_build_fixture_adapter())
        self.assertIsNotNone(result.request_record)

    def test_smoke_response_record_not_none_on_success(self):
        result = execute_e2i_governed_smoke(str(self.db_path), adapter=_build_fixture_adapter())
        self.assertIsNotNone(result.response_record)

    def test_smoke_failure_record_none_on_success(self):
        result = execute_e2i_governed_smoke(str(self.db_path), adapter=_build_fixture_adapter())
        self.assertIsNone(result.failure_record)


# ---------------------------------------------------------------------------
# One-shot smoke payload -- BLOCKED cases
# ---------------------------------------------------------------------------

class LaneE2ISmokepayloadBlockedTests(_DbTestBase):
    def _tf(self):
        return self._write_token_file([self._valid_token_entry()])

    def test_blocked_without_operator_approved(self):
        payload = build_e2i_one_shot_smoke_payload(
            self._tf(), self.db_path, self.backup_proof_path,
            operator_approved=False,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)
        self.assertFalse(payload["executed"])

    def test_blocked_reason_mentions_operator_approved(self):
        payload = build_e2i_one_shot_smoke_payload(
            self._tf(), self.db_path, self.backup_proof_path,
            operator_approved=False,
            adapter=_build_fixture_adapter(),
        )
        reasons = payload.get("blocked_reasons", [])
        self.assertTrue(
            any("operator_approved" in r for r in reasons),
        )

    def test_blocked_without_backup_proof(self):
        payload = build_e2i_one_shot_smoke_payload(
            self._tf(), self.db_path, "/nonexistent/backup.sqlite3",
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_blocked_without_db_path(self):
        payload = build_e2i_one_shot_smoke_payload(
            self._tf(), "/nonexistent/db.sqlite3", self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_blocked_without_token_list(self):
        payload = build_e2i_one_shot_smoke_payload(
            None, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_blocked_with_empty_token_list(self):
        tf = self._write_token_file([])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_blocked_with_non_track_fast_token(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1,
            "lifecycle_lane": "TRACK_NORMAL",
            "approved_by_operator": True,
        }])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_blocked_with_unapproved_token(self):
        tf = self._write_token_file([{
            "token_mint": _MINT_1,
            "lifecycle_lane": "TRACK_FAST",
            "approved_by_operator": False,
        }])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_blocked_payload_has_zero_paper_decisions(self):
        payload = build_e2i_one_shot_smoke_payload(
            self._tf(), self.db_path, self.backup_proof_path,
            operator_approved=False,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["paper_decisions_created"], 0)

    def test_blocked_payload_has_zero_positions(self):
        payload = build_e2i_one_shot_smoke_payload(
            self._tf(), self.db_path, self.backup_proof_path,
            operator_approved=False,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["positions_created"], 0)

    def test_blocked_payload_claude_did_not_run_cycle(self):
        payload = build_e2i_one_shot_smoke_payload(
            self._tf(), self.db_path, self.backup_proof_path,
            operator_approved=False,
            adapter=_build_fixture_adapter(),
        )
        self.assertTrue(payload["claude_did_not_run_cycle"])


# ---------------------------------------------------------------------------
# One-shot smoke payload -- EXECUTED cases (fixture adapter)
# ---------------------------------------------------------------------------

class LaneE2ISmokePayloadExecutedTests(_DbTestBase):
    def _tf(self):
        return self._write_token_file([self._valid_token_entry()])

    def _run(self):
        return build_e2i_one_shot_smoke_payload(
            self._tf(), self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )

    def test_executed_status_is_executed(self):
        self.assertEqual(self._run()["e2i_status"], E2I_STATUS_EXECUTED)

    def test_executed_field_true(self):
        self.assertTrue(self._run()["executed"])

    def test_token_list_valid_true(self):
        self.assertTrue(self._run()["token_list_valid"])

    def test_backup_proof_confirmed_true(self):
        self.assertTrue(self._run()["backup_proof_confirmed"])

    def test_db_path_confirmed_true(self):
        self.assertTrue(self._run()["db_path_confirmed"])

    def test_source_governor_allowed_true(self):
        self.assertTrue(self._run()["source_governor_allowed"])

    def test_request_recorded_true(self):
        self.assertTrue(self._run()["request_recorded"])

    def test_response_recorded_true(self):
        self.assertTrue(self._run()["response_recorded"])

    def test_failure_recorded_false_on_success(self):
        self.assertFalse(self._run()["failure_recorded"])

    def test_before_counts_is_dict(self):
        self.assertIsInstance(self._run()["before_counts"], dict)

    def test_after_counts_is_dict(self):
        self.assertIsInstance(self._run()["after_counts"], dict)

    def test_before_counts_has_source_requests(self):
        self.assertIn("printer_source_requests", self._run()["before_counts"])

    def test_after_counts_has_source_requests(self):
        self.assertIn("printer_source_requests", self._run()["after_counts"])

    def test_after_source_requests_greater_than_before(self):
        payload = self._run()
        before = payload["before_counts"]["printer_source_requests"]
        after = payload["after_counts"]["printer_source_requests"]
        self.assertGreater(after, before)

    def test_paper_decisions_created_zero(self):
        self.assertEqual(self._run()["paper_decisions_created"], 0)

    def test_positions_created_zero(self):
        self.assertEqual(self._run()["positions_created"], 0)

    def test_pnl_created_zero(self):
        self.assertEqual(self._run()["pnl_created"], 0)

    def test_snapshots_created_zero(self):
        self.assertEqual(self._run()["snapshots_created"], 0)

    def test_memories_created_zero(self):
        self.assertEqual(self._run()["memories_created"], 0)

    def test_claude_did_not_run_cycle_true(self):
        self.assertTrue(self._run()["claude_did_not_run_cycle"])

    def test_hard_locks_all_true(self):
        locks = self._run()["hard_locks"]
        for key, val in locks.items():
            self.assertTrue(val, f"hard_locks[{key!r}] must be True")

    def test_no_buy_lock_can_be_false(self):
        self.assertTrue(self._run()["hard_locks"]["no_buy_sell_hold"])

    def test_no_paper_decisions_lock_true(self):
        self.assertTrue(self._run()["hard_locks"]["no_paper_decisions"])

    def test_no_live_trading_lock_true(self):
        self.assertTrue(self._run()["hard_locks"]["no_live_trading"])

    def test_exec_error_none_on_success(self):
        self.assertIsNone(self._run()["exec_error"])

    def test_source_name_is_dexscreener(self):
        self.assertEqual(self._run()["source_name"], "dexscreener")

    def test_payload_json_serializable(self):
        s = json.dumps(self._run())
        self.assertIsInstance(s, str)
        self.assertGreater(len(s), 200)


# ---------------------------------------------------------------------------
# Forbidden table mutation: no paper/snapshot/memory rows written
# ---------------------------------------------------------------------------

class LaneE2IForbiddenTableTests(_DbTestBase):
    def test_no_paper_decisions_written(self):
        before = self._count_rows("printer_paper_decisions")
        tf = self._write_token_file([self._valid_token_entry()])
        build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True, adapter=_build_fixture_adapter(),
        )
        self.assertEqual(self._count_rows("printer_paper_decisions"), before)

    def test_no_paper_positions_written(self):
        before = self._count_rows("printer_paper_positions")
        tf = self._write_token_file([self._valid_token_entry()])
        build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True, adapter=_build_fixture_adapter(),
        )
        self.assertEqual(self._count_rows("printer_paper_positions"), before)

    def test_no_token_snapshots_written(self):
        before = self._count_rows("printer_token_snapshots")
        tf = self._write_token_file([self._valid_token_entry()])
        build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True, adapter=_build_fixture_adapter(),
        )
        self.assertEqual(self._count_rows("printer_token_snapshots"), before)

    def test_no_memories_written(self):
        before = self._count_rows("printer_memories")
        tf = self._write_token_file([self._valid_token_entry()])
        build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True, adapter=_build_fixture_adapter(),
        )
        self.assertEqual(self._count_rows("printer_memories"), before)

    def test_no_memory_windows_written(self):
        before = self._count_rows("printer_memory_windows")
        tf = self._write_token_file([self._valid_token_entry()])
        build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True, adapter=_build_fixture_adapter(),
        )
        self.assertEqual(self._count_rows("printer_memory_windows"), before)


# ---------------------------------------------------------------------------
# CLI tests (fixture adapter injected via _adapter kwarg)
# ---------------------------------------------------------------------------

class LaneE2ICliTests(_DbTestBase):
    def _tf(self):
        return self._write_token_file([self._valid_token_entry()])

    def _run_cli(self, extra_args=None, *, operator_approved=True):
        tf = self._tf()
        args = [
            "--token-list-path", str(tf),
            "--backup-proof-path", str(self.backup_proof_path),
            "--db-path", str(self.db_path),
            "--format", "json",
        ]
        if operator_approved:
            args.append("--operator-approved")
        if extra_args:
            args.extend(extra_args)
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            rc = main_run_e2i_one_shot_governed_source_smoke(
                args, _adapter=_build_fixture_adapter()
            )
        return rc, json.loads(captured.getvalue())

    def test_cli_returns_0(self):
        rc, _ = self._run_cli()
        self.assertEqual(rc, 0)

    def test_cli_outputs_valid_json(self):
        _, payload = self._run_cli()
        self.assertIsInstance(payload, dict)

    def test_cli_payload_has_command_field(self):
        _, payload = self._run_cli()
        self.assertEqual(payload["command"], "printer-run-e2i-one-shot-governed-source-smoke")

    def test_cli_payload_has_e2i_status(self):
        _, payload = self._run_cli()
        self.assertIn("e2i_status", payload)

    def test_cli_executed_on_valid_args(self):
        _, payload = self._run_cli()
        self.assertEqual(payload["e2i_status"], E2I_STATUS_EXECUTED)

    def test_cli_blocked_without_operator_approved(self):
        _, payload = self._run_cli(operator_approved=False)
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_cli_returns_0_when_blocked(self):
        rc, _ = self._run_cli(operator_approved=False)
        self.assertEqual(rc, 0)

    def test_cli_payload_claude_did_not_run_cycle(self):
        _, payload = self._run_cli()
        self.assertTrue(payload["claude_did_not_run_cycle"])


# ---------------------------------------------------------------------------
# E2H integration: transport check delegates to E2I
# ---------------------------------------------------------------------------

class LaneE2IE2HIntegrationTests(unittest.TestCase):
    def test_e2h_transport_check_returns_true(self):
        from printer_v1.operator_cli.e2h_runtime_handler import (
            check_real_source_transport_available as e2h_check,
        )
        ok, _ = e2h_check()
        self.assertTrue(ok, "E2H must delegate to E2I and return True")

    def test_e2h_transport_reason_mentions_e2i_or_dexscreener(self):
        from printer_v1.operator_cli.e2h_runtime_handler import (
            check_real_source_transport_available as e2h_check,
        )
        _, reason = e2h_check()
        self.assertTrue(
            "e2i" in reason.lower() or "dexscreener" in reason.lower(),
        )


# ---------------------------------------------------------------------------
# E2G integration: OPERATOR_RUN_READY after E2I
# ---------------------------------------------------------------------------

class LaneE2IE2GIntegrationTests(_DbTestBase):
    def test_e2g_reports_ready_after_e2i(self):
        from printer_v1.operator_cli.e2g_operator_run import (
            OPERATOR_RUN_READY,
            build_e2g_operator_run_payload,
        )
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(
            payload["first_run_status"], OPERATOR_RUN_READY,
            "E2G must report OPERATOR_RUN_READY after E2I (all gates pass)",
        )

    def test_e2g_runtime_path_exists_true_after_e2i(self):
        from printer_v1.operator_cli.e2g_operator_run import build_e2g_operator_run_payload
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertTrue(payload["runtime_path_exists"])


# ---------------------------------------------------------------------------
# Doc tests
# ---------------------------------------------------------------------------

class LaneE2IDocTests(unittest.TestCase):
    def _doc(self) -> str:
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2i-governed-real-source-transport.md")
        self.assertTrue(path.exists(), f"E2I doc not found: {path}")
        return path.read_text(encoding="utf-8")

    def test_doc_exists(self):
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2i-governed-real-source-transport.md")
        self.assertTrue(path.exists())

    def test_doc_mentions_lane_e2i(self):
        self.assertIn("E2I", self._doc())

    def test_doc_states_claude_did_not_run_cycle(self):
        doc = self._doc()
        self.assertTrue("Claude did not run" in doc or "claude did not" in doc.lower())

    def test_doc_mentions_dexscreener(self):
        self.assertIn("DexScreener", self._doc())

    def test_doc_mentions_source_governor(self):
        self.assertIn("Source Governor", self._doc())

    def test_doc_mentions_hard_locks(self):
        doc = self._doc()
        self.assertTrue("BUY" in doc and "SELL" in doc and "HOLD" in doc)

    def test_doc_mentions_operator_run_ready(self):
        self.assertIn("OPERATOR_RUN_READY", self._doc())

    def test_doc_mentions_one_shot_smoke(self):
        doc = self._doc()
        self.assertTrue("smoke" in doc.lower() or "one-shot" in doc.lower())

    def test_doc_states_no_paper_decisions(self):
        doc = self._doc()
        self.assertTrue("paper decision" in doc.lower() or "printer_paper_decisions" in doc)

    def test_doc_states_no_snapshots(self):
        doc = self._doc()
        self.assertTrue("snapshot" in doc.lower())

    def test_doc_states_no_memories(self):
        doc = self._doc()
        self.assertTrue("memor" in doc.lower())

    def test_doc_mentions_track_fast_first_15m(self):
        self.assertIn("TRACK_FAST_FIRST_15M", self._doc())

    def test_doc_states_free_public_api(self):
        doc = self._doc()
        self.assertTrue("free" in doc.lower() or "public" in doc.lower())

    def test_doc_states_token_specific(self):
        doc = self._doc()
        self.assertTrue("token" in doc.lower() and ("specific" in doc.lower() or "mint" in doc.lower()))

    def test_doc_states_no_generic_search(self):
        doc = self._doc()
        self.assertTrue(
            "generic" in doc.lower() or "q=SOL" in doc or "token_mint" in doc,
            "doc must mention token-specific transport or forbid generic search",
        )


# ---------------------------------------------------------------------------
# Token-specific transport enforcement
# ---------------------------------------------------------------------------

class LaneE2ITokenSpecificTransportTests(_DbTestBase):
    def test_generic_search_forbidden_constant_is_true(self):
        self.assertTrue(_GENERIC_SEARCH_FORBIDDEN)

    def test_e2i_module_source_has_no_q_sol(self):
        import inspect
        import printer_v1.operator_cli.e2i_source_transport as mod
        src = inspect.getsource(mod)
        self.assertNotIn("q=SOL", src, "E2I module must not embed generic q=SOL search URL")

    def test_build_adapter_requires_token_mint(self):
        with self.assertRaises(TypeError):
            build_e2i_dexscreener_adapter()  # missing required keyword-only arg

    def test_build_adapter_rejects_empty_token_mint(self):
        with self.assertRaises(ValueError):
            build_e2i_dexscreener_adapter(token_mint="")

    def test_build_adapter_rejects_placeholder_token_mint(self):
        with self.assertRaises(ValueError):
            build_e2i_dexscreener_adapter(token_mint="PLACEHOLDER_MINT_XYZ")

    def test_build_adapter_with_valid_mint_is_enabled(self):
        adapter = build_e2i_dexscreener_adapter(token_mint=_MINT_1)
        self.assertTrue(adapter.enabled)

    def test_build_adapter_with_valid_mint_has_transport(self):
        adapter = build_e2i_dexscreener_adapter(token_mint=_MINT_1)
        self.assertIsNotNone(adapter.transport)

    def test_execute_without_adapter_requires_token_mint(self):
        from printer_v1.sources.dexscreener import DexScreenerAdapter
        adapter = build_e2i_dexscreener_adapter(token_mint=_MINT_1)
        # Providing adapter bypasses token_mint requirement — verify ValueError when both missing
        with self.assertRaises(ValueError):
            execute_e2i_governed_smoke(str(self.db_path), adapter=None, token_mint="")

    def test_executed_payload_has_approved_token_mint(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["approved_token_mint"], _MINT_1)

    def test_approved_token_mint_in_payload_matches_token_list(self):
        tf = self._write_token_file([self._valid_token_entry(_MINT_1)])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertIn(_MINT_1, payload.get("approved_token_mint", ""))

    def test_smoke_target_includes_approved_token_mint(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        target = payload.get("smoke_target", "")
        self.assertIn(_MINT_1, target, "smoke_target must contain the approved token mint")

    def test_smoke_target_is_not_generic_sol_search(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        target = payload.get("smoke_target", "")
        self.assertNotIn("q=SOL", target, "smoke_target must not be generic SOL search")

    def test_generic_search_used_is_false_when_executed(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertFalse(payload.get("generic_search_used", True))

    def test_generic_search_used_is_false_when_blocked(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=False,
            adapter=_build_fixture_adapter(),
        )
        self.assertFalse(payload.get("generic_search_used", True))

    def test_blocked_payload_has_no_approved_token_mint(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=False,
            adapter=_build_fixture_adapter(),
        )
        self.assertIsNone(payload.get("approved_token_mint"))

    def test_more_than_one_track_fast_token_blocked(self):
        mint_a = "AToken111111111111111111111111111111111111111"
        mint_b = "BToken222222222222222222222222222222222222222"
        tf = self._write_token_file([
            self._valid_token_entry(mint_a),
            self._valid_token_entry(mint_b),
        ])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertEqual(payload["e2i_status"], E2I_STATUS_BLOCKED)

    def test_no_broad_discovery_both_states(self):
        tf = self._write_token_file([self._valid_token_entry()])
        for approved in [True, False]:
            with self.subTest(approved=approved):
                payload = build_e2i_one_shot_smoke_payload(
                    tf, self.db_path, self.backup_proof_path,
                    operator_approved=approved,
                    adapter=_build_fixture_adapter(),
                )
                self.assertFalse(payload.get("generic_search_used", True))

    def test_dexscreener_token_url_template_exists(self):
        from printer_v1.sources.dexscreener import DEXSCREENER_TOKEN_URL_TEMPLATE
        self.assertIn("{token_mint}", DEXSCREENER_TOKEN_URL_TEMPLATE)
        self.assertNotIn("q=SOL", DEXSCREENER_TOKEN_URL_TEMPLATE)

    def test_dexscreener_token_url_contains_mint_when_formatted(self):
        from printer_v1.sources.dexscreener import DEXSCREENER_TOKEN_URL_TEMPLATE
        url = DEXSCREENER_TOKEN_URL_TEMPLATE.format(token_mint=_MINT_1)
        self.assertIn(_MINT_1, url)
        self.assertNotIn("q=SOL", url)

    def test_build_dexscreener_token_transport_exists(self):
        from printer_v1.sources.dexscreener import build_dexscreener_token_transport
        transport = build_dexscreener_token_transport(_MINT_1)
        self.assertTrue(callable(transport))

    def test_no_hard_lock_can_be_false(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        locks = payload["hard_locks"]
        for key, val in locks.items():
            self.assertTrue(val, f"hard_locks[{key!r}] must be True, was {val!r}")

    def test_hard_locks_includes_no_generic_search(self):
        tf = self._write_token_file([self._valid_token_entry()])
        payload = build_e2i_one_shot_smoke_payload(
            tf, self.db_path, self.backup_proof_path,
            operator_approved=True,
            adapter=_build_fixture_adapter(),
        )
        self.assertIn("no_generic_search", payload["hard_locks"])
        self.assertTrue(payload["hard_locks"]["no_generic_search"])
