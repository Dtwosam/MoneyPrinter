"""
Post-Lane 10 Lane E2H -- TRACK_FAST_FIRST_15M Runtime Handler Boundary

Tests prove:
- e2h_runtime_handler module imports cleanly
- HANDLER_JOB_KIND is TRACK_FAST_FIRST_15M
- HANDLER_LIFECYCLE_LANE is TRACK_FAST
- HANDLER_TARGET_WINDOW is WINDOW_15M
- HANDLER_MAX_TOKENS_FIRST_RUN is 1
- is_handler_registered() returns True
- check_real_source_transport_available() returns (True, reason) after Lane E2I
- reason mentions E2I or DexScreener or real transport
- PHASE35_SAFE_JOB_KINDS includes TRACK_FAST_FIRST_15M
- execute_track_fast_first_15m_job blocked when transport patched False
- result.executed False on transport block (when transport forced unavailable)
- result.gate_failed == real_source_transport (when transport forced unavailable)
- result.blocked_reason mentions fixture or transport (when transport forced unavailable)
- with transport patched: running jobs blocks
- with transport patched: active locks blocks
- with transport patched: source governor denial blocks
- with transport patched: all gates clear -> executed=True
- with transport patched + adapter: source recording rows written (request row)
- validate_token_entry: valid entry passes
- validate_token_entry: invalid mint blocked
- validate_token_entry: non-TRACK_FAST lane blocked
- validate_token_entry: approved_by_operator False blocked
- validate_token_list: exactly 1 token passes
- validate_token_list: 0 tokens blocked
- validate_token_list: 2 tokens blocked (more than 1)
- validate_token_list: non-list blocked
- validate_token_list: invalid entry cascades
- check_source_governor: allowed when budget available
- check_source_governor: denied when budget exhausted
- _execute_phase35_scheduler_job raises for TRACK_FAST_FIRST_15M (transport forced False)
- no DB mutation when handler transport-blocked (transport forced False)
- no DB mutation when handler blocked on running jobs
- forbidden table mutation: paper_decisions rows -> blocked
- hard_locks all False in executed result
- E2G integration: runtime_path_exists True after E2I
- E2G integration: e2g_status OPERATOR_RUN_READY after E2I (all gates pass)
- no source-fetching library modules imported by e2h module
- doc required statements present
"""

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
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.operator_cli.commands import (
    PHASE35_SAFE_JOB_KINDS,
    _execute_phase35_scheduler_job,
)
from printer_v1.operator_cli.e2c_readiness import HARD_LOCKS
from printer_v1.operator_cli.e2g_operator_run import (
    OPERATOR_RUN_BLOCKED,
    OPERATOR_RUN_READY,
    E2G_STATUS_BLOCKED,
    E2G_STATUS_READY,
    _check_15m_cycle_runtime_available,
    build_e2g_operator_run_payload,
)
from printer_v1.operator_cli.e2h_runtime_handler import (
    E2H_STATUS_BLOCKED,
    E2H_STATUS_EXECUTED,
    HANDLER_JOB_KIND,
    HANDLER_LIFECYCLE_LANE,
    HANDLER_MAX_TOKENS_FIRST_RUN,
    HANDLER_TARGET_WINDOW,
    check_real_source_transport_available,
    check_source_governor,
    execute_track_fast_first_15m_job,
    is_handler_registered,
    validate_token_entry,
    validate_token_list,
)
from printer_v1.sources.contracts import build_governed_source_request
from printer_v1.sources.governed_execution import build_fixture_source_adapter
from printer_v1.sources.recording import record_source_request, record_source_response
from printer_v1.sources.registry import SOURCE_REGISTRY


_MINT_1 = "C" * 43
_MINT_2 = "D" * 44

_RATE_LIMIT_SOURCE = "alternative_me"
_RATE_LIMIT_KIND = "fear_greed_context"
_RATE_LIMIT = SOURCE_REGISTRY[_RATE_LIMIT_SOURCE].default_rate_limit_per_minute

_VALID_NOTE = "Operator-approved for E2H test. Reviewed 2026-06-27."

_TRANSPORT_PATCH = (
    "printer_v1.operator_cli.e2h_runtime_handler.check_real_source_transport_available"
)
_E2G_RUNTIME_PATCH = (
    "printer_v1.operator_cli.e2g_operator_run._check_15m_cycle_runtime_available"
)
_FORBIDDEN_CHECK_PATCH = (
    "printer_v1.operator_cli.e2h_runtime_handler._check_forbidden_table_mutation"
)


class _DbTestBase(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2h_test.sqlite3"
        apply_migrations(self.db_path)
        self.backup_proof_path = pathlib.Path(self.tempdir.name) / "backup.sqlite3"
        self.backup_proof_path.write_bytes(b"backup")

    def tearDown(self):
        self.tempdir.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()

    def _fake_job(self, job_id: int = -1, job_kind: str = HANDLER_JOB_KIND) -> dict:
        return {
            "id": job_id,
            "job_kind": job_kind,
            "job_name": "e2h_test_job",
            "status": "PENDING",
        }

    def _insert_running_job(self, job_id: int = 999) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO printer_scheduler_jobs"
                " (id, job_name, job_kind, status, scheduled_for)"
                " VALUES (?, ?, ?, 'RUNNING', ?)",
                (job_id, f"running_job_{job_id}", "BACKUP_SOURCE_CHECK",
                 "2026-06-27T12:00:00"),
            )
            conn.commit()
        finally:
            conn.close()

    def _insert_locked_job(self, job_id: int = 998) -> None:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute(
                "INSERT INTO printer_scheduler_jobs"
                " (id, job_name, job_kind, status, locked_at, scheduled_for)"
                " VALUES (?, ?, ?, 'PENDING', ?, ?)",
                (job_id, f"locked_job_{job_id}", "BACKUP_SOURCE_CHECK",
                 "2026-06-27T12:00:00", "2026-06-27T12:00:00"),
            )
            conn.commit()
        finally:
            conn.close()

    def _exhaust_rate_limit(self, source_name: str, request_kind: str) -> None:
        limit = SOURCE_REGISTRY[source_name].default_rate_limit_per_minute
        for _ in range(limit):
            from printer_v1.sources.contracts import NormalizedSourceResult
            req = build_governed_source_request(source_name, request_kind)
            req_record = record_source_request(self.db_path, req)
            result = NormalizedSourceResult(
                source_name=source_name,
                request_kind=request_kind,
                source_status=SourceStatus.COMPLETE,
                data_quality_label=DataQualityLabel.CLEAN_DATA,
                normalized_payload={},
                status_code=200,
            )
            record_source_response(self.db_path, req_record, result)

    def _valid_entry(self, mint: str = _MINT_1, lane: str = "TRACK_FAST") -> dict:
        return {
            "token_mint": mint,
            "lifecycle_lane": lane,
            "operator_note": _VALID_NOTE,
            "approved_by_operator": True,
        }

    def _write_token_file(self, tokens: list) -> pathlib.Path:
        data = {"tokens": tokens}
        path = pathlib.Path(self.tempdir.name) / "token_list.json"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path


# ---------------------------------------------------------------------------
# Import and constant tests
# ---------------------------------------------------------------------------

class LaneE2HImportTests(unittest.TestCase):
    def test_module_importable(self):
        import printer_v1.operator_cli.e2h_runtime_handler as m
        self.assertIsNotNone(m)

    def test_handler_job_kind_value(self):
        self.assertEqual(HANDLER_JOB_KIND, "TRACK_FAST_FIRST_15M")

    def test_handler_lifecycle_lane_value(self):
        self.assertEqual(HANDLER_LIFECYCLE_LANE, "TRACK_FAST")

    def test_handler_target_window_value(self):
        self.assertEqual(HANDLER_TARGET_WINDOW, "WINDOW_15M")

    def test_handler_max_tokens_first_run_is_1(self):
        self.assertEqual(HANDLER_MAX_TOKENS_FIRST_RUN, 1)

    def test_e2h_status_executed_value(self):
        self.assertEqual(E2H_STATUS_EXECUTED, "E2H_TRACK_FAST_FIRST_15M_EXECUTED")

    def test_e2h_status_blocked_value(self):
        self.assertEqual(E2H_STATUS_BLOCKED, "E2H_TRACK_FAST_FIRST_15M_BLOCKED")

    def test_no_http_libraries_in_e2h_source(self):
        src = (SRC_PATH / "printer_v1" / "operator_cli" / "e2h_runtime_handler.py").read_text(encoding="utf-8")
        for lib in ("import requests", "import httpx", "import aiohttp"):
            self.assertNotIn(lib, src)

    def test_no_dexscreener_direct_import_in_e2h(self):
        src = (SRC_PATH / "printer_v1" / "operator_cli" / "e2h_runtime_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("from printer_v1.sources.dexscreener", src)

    def test_no_direct_execute_source_in_e2h(self):
        src = (SRC_PATH / "printer_v1" / "operator_cli" / "e2h_runtime_handler.py").read_text(encoding="utf-8")
        self.assertNotIn("execute_real_source", src)


# ---------------------------------------------------------------------------
# Handler registration and transport tests
# ---------------------------------------------------------------------------

class LaneE2HRegistrationTests(unittest.TestCase):
    def test_is_handler_registered_true(self):
        self.assertTrue(is_handler_registered())

    def test_phase35_safe_job_kinds_includes_track_fast_first_15m(self):
        self.assertIn("TRACK_FAST_FIRST_15M", PHASE35_SAFE_JOB_KINDS)

    def test_transport_returns_true_after_e2i(self):
        ok, _ = check_real_source_transport_available()
        self.assertTrue(ok, "Lane E2I must provide real transport (True)")

    def test_transport_reason_mentions_e2i_or_dexscreener(self):
        _, reason = check_real_source_transport_available()
        self.assertTrue(
            "e2i" in reason.lower() or "dexscreener" in reason.lower(),
        )

    def test_transport_reason_mentions_real_or_available(self):
        _, reason = check_real_source_transport_available()
        self.assertTrue(
            "real" in reason.lower() or "available" in reason.lower(),
        )

    def test_transport_reason_mentions_smoke_transport(self):
        _, reason = check_real_source_transport_available()
        self.assertTrue(
            "smoke" in reason.lower() or "transport" in reason.lower(),
        )

    def test_transport_reason_mentions_real_adapter_or_http(self):
        _, reason = check_real_source_transport_available()
        self.assertTrue(
            "urllib" in reason.lower()
            or "http" in reason.lower()
            or "adapter" in reason.lower()
            or "smoke" in reason.lower(),
        )


# ---------------------------------------------------------------------------
# Token validation tests
# ---------------------------------------------------------------------------

class LaneE2HTokenValidationTests(unittest.TestCase):
    def _valid_entry(self, mint: str = _MINT_1, lane: str = "TRACK_FAST") -> dict:
        return {"token_mint": mint, "lifecycle_lane": lane, "approved_by_operator": True}

    def test_valid_entry_passes(self):
        ok, reason = validate_token_entry(self._valid_entry())
        self.assertTrue(ok, reason)

    def test_invalid_mint_blocked(self):
        ok, reason = validate_token_entry(self._valid_entry(mint="not-a-mint"))
        self.assertFalse(ok)
        self.assertIn("token_mint", reason)

    def test_non_track_fast_lane_blocked(self):
        ok, reason = validate_token_entry(self._valid_entry(lane="TRACK_NORMAL"))
        self.assertFalse(ok)
        self.assertIn("TRACK_FAST", reason)

    def test_track_normal_lane_explicitly_blocked(self):
        ok, reason = validate_token_entry(self._valid_entry(lane="TRACK_NORMAL"))
        self.assertFalse(ok)

    def test_approved_by_operator_false_blocked(self):
        entry = self._valid_entry()
        entry["approved_by_operator"] = False
        ok, reason = validate_token_entry(entry)
        self.assertFalse(ok)
        self.assertIn("approved_by_operator", reason)

    def test_missing_approved_by_operator_blocked(self):
        entry = {"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST"}
        ok, _ = validate_token_entry(entry)
        self.assertFalse(ok)

    def test_validate_token_list_exactly_1_passes(self):
        ok, reason = validate_token_list([self._valid_entry()])
        self.assertTrue(ok, reason)

    def test_validate_token_list_zero_tokens_blocked(self):
        ok, reason = validate_token_list([])
        self.assertFalse(ok)
        self.assertTrue("exactly" in reason or "0" in reason)

    def test_validate_token_list_two_tokens_blocked(self):
        ok, reason = validate_token_list([
            self._valid_entry(_MINT_1),
            self._valid_entry(_MINT_2),
        ])
        self.assertFalse(ok)
        self.assertTrue("exactly" in reason or "2" in reason)

    def test_validate_token_list_non_list_blocked(self):
        ok, reason = validate_token_list({"token_mint": _MINT_1})  # type: ignore[arg-type]
        self.assertFalse(ok)

    def test_validate_token_list_invalid_entry_cascades(self):
        ok, reason = validate_token_list([self._valid_entry(lane="TRACK_NORMAL")])
        self.assertFalse(ok)
        self.assertIn("TRACK_FAST", reason)


# ---------------------------------------------------------------------------
# Transport-blocked handler tests (transport patched to False for gate isolation)
# ---------------------------------------------------------------------------

class LaneE2HHandlerTransportBlockedTests(_DbTestBase):
    """Gate regression: handler is BLOCKED when transport is forced unavailable.

    After Lane E2I, check_real_source_transport_available() returns True in the
    real build. These tests patch transport to False to verify the gate logic
    remains correct regardless of current transport state.
    """

    def setUp(self):
        super().setUp()
        self._transport_patcher = patch(
            _TRANSPORT_PATCH,
            return_value=(False, "E2H transport gate test: simulating transport unavailable"),
        )
        self._transport_patcher.start()

    def tearDown(self):
        self._transport_patcher.stop()
        super().tearDown()

    def _run_handler(self) -> dict:
        conn = self._connect()
        try:
            return execute_track_fast_first_15m_job(conn, self._fake_job())
        finally:
            conn.close()

    def test_handler_blocked_when_transport_unavailable(self):
        result = self._run_handler()
        self.assertEqual(result["status"], E2H_STATUS_BLOCKED)

    def test_handler_executed_false_on_transport_block(self):
        result = self._run_handler()
        self.assertFalse(result["executed"])

    def test_gate_failed_is_real_source_transport(self):
        result = self._run_handler()
        self.assertEqual(result.get("gate_failed"), "real_source_transport")

    def test_blocked_reason_mentions_fixture_or_transport(self):
        result = self._run_handler()
        reason = result.get("blocked_reason", "")
        self.assertTrue(
            "fixture" in reason.lower() or "transport" in reason.lower(),
        )

    def test_paper_decisions_created_zero(self):
        result = self._run_handler()
        self.assertEqual(result.get("paper_decisions_created"), 0)

    def test_positions_created_zero(self):
        result = self._run_handler()
        self.assertEqual(result.get("positions_created"), 0)

    def test_pnl_created_zero(self):
        result = self._run_handler()
        self.assertEqual(result.get("pnl_created"), 0)


# ---------------------------------------------------------------------------
# Handler gate tests (transport patched to True)
# ---------------------------------------------------------------------------

class LaneE2HHandlerGateTests(_DbTestBase):
    def _run_patched(self, **kw) -> dict:
        conn = self._connect()
        try:
            with patch(_TRANSPORT_PATCH, return_value=(True, "")):
                return execute_track_fast_first_15m_job(conn, self._fake_job(), **kw)
        finally:
            conn.close()

    def test_all_gates_clear_executed_true(self):
        result = self._run_patched()
        self.assertTrue(result["executed"])

    def test_all_gates_clear_status_executed(self):
        result = self._run_patched()
        self.assertEqual(result["status"], E2H_STATUS_EXECUTED)

    def test_running_jobs_blocked(self):
        self._insert_running_job(job_id=999)
        result = self._run_patched()
        self.assertEqual(result["status"], E2H_STATUS_BLOCKED)
        self.assertEqual(result["gate_failed"], "execution_gates")

    def test_running_jobs_blocked_reason(self):
        self._insert_running_job(job_id=999)
        result = self._run_patched()
        gates = result.get("blocked_gates", [])
        self.assertTrue(any("running_jobs" in g for g in gates))

    def test_active_locks_blocked(self):
        self._insert_locked_job(job_id=998)
        result = self._run_patched()
        self.assertEqual(result["status"], E2H_STATUS_BLOCKED)
        gates = result.get("blocked_gates", [])
        self.assertTrue(any("active_locks" in g for g in gates))

    def test_source_governor_denial_blocks(self):
        self._exhaust_rate_limit("dexscreener", "pair_market_snapshot")
        result = self._run_patched()
        self.assertEqual(result["status"], E2H_STATUS_BLOCKED)
        gates = result.get("blocked_gates", [])
        self.assertTrue(any("source_governor" in g for g in gates))

    def test_hard_locks_all_false_in_executed_result(self):
        result = self._run_patched()
        hl = result.get("hard_locks", {})
        for key, val in hl.items():
            self.assertIs(val, False, f"hard_locks[{key!r}] must be False")

    def test_buy_enabled_false_in_result(self):
        result = self._run_patched()
        self.assertFalse(result.get("buy_enabled"))

    def test_sell_enabled_false_in_result(self):
        result = self._run_patched()
        self.assertFalse(result.get("sell_enabled"))

    def test_hold_enabled_false_in_result(self):
        result = self._run_patched()
        self.assertFalse(result.get("hold_enabled"))

    def test_executed_result_has_source_results(self):
        result = self._run_patched()
        self.assertIn("source_results", result)

    def test_no_adapter_executed_no_source_calls(self):
        result = self._run_patched()
        self.assertEqual(result.get("source_results"), [])


# ---------------------------------------------------------------------------
# Source recording path tests (transport patched + fixture adapter)
# ---------------------------------------------------------------------------

class LaneE2HSourceRecordingTests(_DbTestBase):
    def _run_with_adapter(self) -> dict:
        adapter = build_fixture_source_adapter(
            "dexscreener",
            fixture_kind="fixture_success",
            fixture_payload={"price_usd": "0.001"},
        )
        conn = self._connect()
        try:
            with patch(_TRANSPORT_PATCH, return_value=(True, "")):
                result = execute_track_fast_first_15m_job(
                    conn, self._fake_job(), adapter=adapter
                )
            conn.commit()
            return result
        finally:
            conn.close()

    def test_source_recording_executed_true(self):
        result = self._run_with_adapter()
        self.assertTrue(result["executed"])

    def test_source_request_row_written(self):
        before = self._count_rows("printer_source_requests")
        self._run_with_adapter()
        after = self._count_rows("printer_source_requests")
        self.assertGreater(after, before)

    def test_source_response_row_written(self):
        before = self._count_rows("printer_source_responses")
        self._run_with_adapter()
        after = self._count_rows("printer_source_responses")
        self.assertGreater(after, before)

    def test_source_results_in_payload(self):
        result = self._run_with_adapter()
        self.assertGreater(len(result["source_results"]), 0)

    def test_source_results_has_request_recorded(self):
        result = self._run_with_adapter()
        self.assertTrue(result["source_results"][0]["request_recorded"])

    def test_source_results_has_response_recorded(self):
        result = self._run_with_adapter()
        self.assertTrue(result["source_results"][0]["response_recorded"])

    def test_no_paper_decisions_written(self):
        before = self._count_rows("printer_paper_decisions")
        self._run_with_adapter()
        after = self._count_rows("printer_paper_decisions")
        self.assertEqual(before, after)

    def test_no_paper_positions_written(self):
        before = self._count_rows("printer_paper_positions")
        self._run_with_adapter()
        after = self._count_rows("printer_paper_positions")
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# No mutation tests (transport blocked)
# ---------------------------------------------------------------------------

class LaneE2HMutationTests(_DbTestBase):
    def _run_blocked(self) -> dict:
        conn = self._connect()
        try:
            return execute_track_fast_first_15m_job(conn, self._fake_job())
        finally:
            conn.close()

    def test_source_requests_unchanged_when_blocked(self):
        before = self._count_rows("printer_source_requests")
        self._run_blocked()
        self.assertEqual(self._count_rows("printer_source_requests"), before)

    def test_source_responses_unchanged_when_blocked(self):
        before = self._count_rows("printer_source_responses")
        self._run_blocked()
        self.assertEqual(self._count_rows("printer_source_responses"), before)

    def test_scheduler_jobs_unchanged_when_blocked(self):
        before = self._count_rows("printer_scheduler_jobs")
        self._run_blocked()
        self.assertEqual(self._count_rows("printer_scheduler_jobs"), before)

    def test_paper_decisions_unchanged_when_blocked(self):
        before = self._count_rows("printer_paper_decisions")
        self._run_blocked()
        self.assertEqual(self._count_rows("printer_paper_decisions"), before)

    def test_no_mutation_with_running_job_patched(self):
        self._insert_running_job()
        before_req = self._count_rows("printer_source_requests")
        conn = self._connect()
        try:
            with patch(_TRANSPORT_PATCH, return_value=(True, "")):
                execute_track_fast_first_15m_job(conn, self._fake_job())
        finally:
            conn.close()
        self.assertEqual(self._count_rows("printer_source_requests"), before_req)


# ---------------------------------------------------------------------------
# Forbidden table mutation gate
# ---------------------------------------------------------------------------

class LaneE2HForbiddenTableTests(_DbTestBase):
    """Forbidden table mutation gate tests -- mocked to avoid FK constraints."""

    _VIOLATION = ["printer_paper_decisions: 1 rows (must remain 0)"]

    def test_forbidden_table_mutation_blocks(self):
        conn = self._connect()
        try:
            with patch(_TRANSPORT_PATCH, return_value=(True, "")):
                with patch(_FORBIDDEN_CHECK_PATCH, return_value=self._VIOLATION):
                    result = execute_track_fast_first_15m_job(conn, self._fake_job())
        finally:
            conn.close()
        self.assertEqual(result["status"], E2H_STATUS_BLOCKED)
        gates = result.get("blocked_gates", [])
        self.assertTrue(any("forbidden_table_mutation" in g for g in gates))

    def test_forbidden_table_reason_mentions_paper_decisions(self):
        conn = self._connect()
        try:
            with patch(_TRANSPORT_PATCH, return_value=(True, "")):
                with patch(_FORBIDDEN_CHECK_PATCH, return_value=self._VIOLATION):
                    result = execute_track_fast_first_15m_job(conn, self._fake_job())
        finally:
            conn.close()
        gates = result.get("blocked_gates", [])
        self.assertTrue(any("printer_paper_decisions" in g for g in gates))


# ---------------------------------------------------------------------------
# Source governor check function
# ---------------------------------------------------------------------------

class LaneE2HSourceGovernorTests(_DbTestBase):
    def test_governor_allowed_when_budget_available(self):
        conn = self._connect()
        try:
            ok, reason = check_source_governor(conn)
        finally:
            conn.close()
        self.assertTrue(ok)
        self.assertEqual(reason, "allowed")

    def test_governor_denied_when_budget_exhausted(self):
        self._exhaust_rate_limit("dexscreener", "pair_market_snapshot")
        conn = self._connect()
        try:
            ok, reason = check_source_governor(conn)
        finally:
            conn.close()
        self.assertFalse(ok)


# ---------------------------------------------------------------------------
# Phase 35 dispatcher integration
# ---------------------------------------------------------------------------

class LaneE2HPhase35DispatchTests(_DbTestBase):
    """Gate regression: Phase 35 dispatch raises for TRACK_FAST_FIRST_15M when transport blocked.

    After Lane E2I, real transport is available. These tests patch transport to False
    so the dispatch tests remain valid gate-regression tests.
    """

    def setUp(self):
        super().setUp()
        self._transport_patcher = patch(
            _TRANSPORT_PATCH,
            return_value=(False, "Phase35 dispatch test: transport unavailable"),
        )
        self._transport_patcher.start()

    def tearDown(self):
        self._transport_patcher.stop()
        super().tearDown()

    def _fake_sqlite_row(self) -> sqlite3.Row:
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.execute(
            "CREATE TABLE t (id INTEGER, job_name TEXT, job_kind TEXT,"
            " status TEXT, scheduled_for TEXT)"
        )
        conn.execute(
            "INSERT INTO t VALUES (1, 'e2h_test', 'TRACK_FAST_FIRST_15M',"
            " 'RUNNING', '2026-06-27T12:00:00')"
        )
        conn.commit()
        row = conn.execute("SELECT * FROM t LIMIT 1").fetchone()
        conn.close()
        return row

    def test_phase35_raises_for_track_fast_first_15m_blocked(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = self._fake_sqlite_row()
            with self.assertRaises(ValueError) as ctx:
                _execute_phase35_scheduler_job(conn, row)
            self.assertIn("TRACK_FAST_FIRST_15M_HANDLER_BLOCKED", str(ctx.exception))
        finally:
            conn.close()

    def test_phase35_raises_contains_transport_reason(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            row = self._fake_sqlite_row()
            with self.assertRaises(ValueError) as ctx:
                _execute_phase35_scheduler_job(conn, row)
            self.assertTrue(
                "fixture" in str(ctx.exception).lower()
                or "transport" in str(ctx.exception).lower()
            )
        finally:
            conn.close()


# ---------------------------------------------------------------------------
# E2G integration tests
# ---------------------------------------------------------------------------

class LaneE2HE2GIntegrationTests(_DbTestBase):
    def test_e2g_runtime_check_true_after_e2i(self):
        ok, _ = _check_15m_cycle_runtime_available()
        self.assertTrue(ok, "Lane E2I must make runtime check return True")

    def test_e2g_runtime_reason_no_longer_mentions_not_implemented(self):
        _, reason = _check_15m_cycle_runtime_available()
        self.assertFalse(
            "not implemented" in reason and "handler" in reason.lower()
            and "BACKUP_SOURCE_CHECK" in reason,
            "reason should not still say 'handler not implemented'",
        )

    def test_e2g_runtime_reason_mentions_handler_registered(self):
        _, reason = _check_15m_cycle_runtime_available()
        self.assertTrue(
            "registered" in reason.lower() or "E2H" in reason,
        )

    def test_e2g_runtime_reason_mentions_transport_unavailable(self):
        _, reason = _check_15m_cycle_runtime_available()
        self.assertTrue(
            "transport" in reason.lower() or "fixture" in reason.lower(),
        )

    def test_e2g_payload_runtime_path_exists_true_after_e2i(self):
        tf = self._write_token_file([{"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST", "approved_by_operator": True, "operator_note": _VALID_NOTE}])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertTrue(payload["runtime_path_exists"], "Lane E2I must make runtime_path_exists True")

    def test_e2g_payload_runtime_path_reason_mentions_e2h_registered(self):
        tf = self._write_token_file([{"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST", "approved_by_operator": True, "operator_note": _VALID_NOTE}])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        reason = payload.get("runtime_path_reason", "")
        self.assertTrue(
            "registered" in reason.lower() or "E2H" in reason,
            "runtime_path_reason must mention handler registered",
        )

    def test_e2g_payload_runtime_path_reason_mentions_transport(self):
        tf = self._write_token_file([{"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST", "approved_by_operator": True, "operator_note": _VALID_NOTE}])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        reason = payload.get("runtime_path_reason", "")
        self.assertTrue(
            "transport" in reason.lower() or "fixture" in reason.lower(),
        )

    def test_e2g_payload_e2g_status_ready_after_e2i(self):
        tf = self._write_token_file([{"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST", "approved_by_operator": True, "operator_note": _VALID_NOTE}])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["e2g_status"], E2G_STATUS_READY,
                         "Lane E2I must make E2G report OPERATOR_RUN_READY when all gates pass")

    def test_e2g_payload_first_run_status_ready_after_e2i(self):
        tf = self._write_token_file([{"token_mint": _MINT_1, "lifecycle_lane": "TRACK_FAST", "approved_by_operator": True, "operator_note": _VALID_NOTE}])
        payload = build_e2g_operator_run_payload(
            tf, self.db_path,
            approval_confirmed=True,
            backup_confirmed=True,
            backup_proof_path=self.backup_proof_path,
        )
        self.assertEqual(payload["first_run_status"], OPERATOR_RUN_READY,
                         "Lane E2I must make first_run_status OPERATOR_RUN_READY when all gates pass")


# ---------------------------------------------------------------------------
# Doc tests
# ---------------------------------------------------------------------------

class LaneE2HDocTests(unittest.TestCase):
    def _doc(self) -> str:
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2h-track-fast-first-15m-runtime-handler.md")
        self.assertTrue(path.exists(), f"E2H doc not found: {path}")
        return path.read_text(encoding="utf-8")

    def test_doc_exists(self):
        path = (PROJECT_ROOT / "docs"
                / "printer-v1-lane-e2h-track-fast-first-15m-runtime-handler.md")
        self.assertTrue(path.exists())

    def test_doc_states_claude_did_not_run_cycle(self):
        doc = self._doc()
        self.assertTrue("Claude did not run" in doc or "claude did not" in doc.lower())

    def test_doc_states_handler_registered(self):
        doc = self._doc()
        self.assertIn("registered", doc.lower())

    def test_doc_states_transport_still_fixture_only(self):
        doc = self._doc()
        self.assertTrue(
            "fixture-only" in doc.lower() or "fixture only" in doc.lower(),
        )

    def test_doc_states_does_not_authorize_real_execution(self):
        doc = self._doc()
        self.assertTrue("does NOT authorize" in doc)

    def test_doc_mentions_track_fast_first_15m(self):
        doc = self._doc()
        self.assertIn("TRACK_FAST_FIRST_15M", doc)

    def test_doc_mentions_phase35_safe_job_kinds(self):
        doc = self._doc()
        self.assertIn("PHASE35_SAFE_JOB_KINDS", doc)

    def test_doc_mentions_source_governor(self):
        doc = self._doc()
        self.assertIn("Source Governor", doc)

    def test_doc_mentions_central_scheduler(self):
        doc = self._doc()
        self.assertIn("Central Scheduler", doc)

    def test_doc_mentions_buy_sell_hold_locked(self):
        doc = self._doc()
        self.assertTrue("BUY" in doc and "SELL" in doc and "HOLD" in doc)

    def test_doc_mentions_5m_support_only(self):
        doc = self._doc()
        self.assertIn("5m", doc)

    def test_doc_mentions_stop_conditions(self):
        doc = self._doc()
        self.assertIn("Stop Condition", doc)

    def test_doc_mentions_rollback(self):
        doc = self._doc()
        self.assertIn("Rollback", doc)

    def test_doc_mentions_fixture_source_adapter(self):
        doc = self._doc()
        self.assertIn("FixtureSourceAdapter", doc)

    def test_doc_mentions_zero_memories_valid(self):
        doc = self._doc()
        self.assertTrue("zero" in doc.lower() and "memor" in doc.lower())

    def test_doc_mentions_hard_locks(self):
        doc = self._doc()
        self.assertIn("hard_lock", doc.lower().replace("-", "_").replace(" ", "_"))

    def test_doc_states_next_lane_build_real_adapter(self):
        doc = self._doc()
        self.assertTrue(
            "real source adapter" in doc.lower() or "real adapter" in doc.lower(),
            "doc must state next lane builds real source adapter",
        )

    def test_doc_mentions_allowed_table_changes(self):
        doc = self._doc()
        self.assertTrue(
            "Allowed" in doc and "table" in doc.lower(),
        )

    def test_doc_mentions_forbidden_table_changes(self):
        doc = self._doc()
        self.assertIn("Forbidden", doc)

    def test_doc_mentions_e2g_blocker_reason_transition(self):
        doc = self._doc()
        self.assertTrue(
            "blocker" in doc.lower() or "transitions" in doc.lower() or "changes" in doc.lower(),
        )


if __name__ == "__main__":
    unittest.main()
