"""
Post-Lane 10 Lane E2J -- First Bounded 15m Cycle Operator Execution

Tests prove:
- e2j_first_15m_cycle module imports cleanly
- E2J_CYCLE_JOB_KIND is "TRACK_FAST_FIRST_15M"
- E2J_LOCK_OWNER defined and non-empty
- E2J_JOB_NAME defined and non-empty
- E2J_STATUS_EXECUTED and E2J_STATUS_BLOCKED defined
- _AUDIT_TABLES is defined and non-empty
- _FORBIDDEN_DELTA_TABLES is defined and non-empty
- _HARD_LOCKS is defined and non-empty
- _HARD_LOCKS no_buy_sell_hold is True
- _HARD_LOCKS no_paper_decisions is True
- _HARD_LOCKS no_positions is True
- _HARD_LOCKS no_pnl is True
- _HARD_LOCKS no_live_trading is True
- _HARD_LOCKS no_paid_api is True
- _HARD_LOCKS no_generic_search is True
- build_e2j_first_15m_cycle_payload: blocked when operator_approved=False
- build_e2j_first_15m_cycle_payload: blocked when db_path is None
- build_e2j_first_15m_cycle_payload: blocked when db_path missing file
- build_e2j_first_15m_cycle_payload: blocked when backup_proof_path is None
- build_e2j_first_15m_cycle_payload: blocked when backup_proof_path missing
- build_e2j_first_15m_cycle_payload: blocked when token_list_path is None
- build_e2j_first_15m_cycle_payload: blocked when token list invalid
- build_e2j_first_15m_cycle_payload: blocked status is E2J_STATUS_BLOCKED
- build_e2j_first_15m_cycle_payload: blocked payload has executed=False
- build_e2j_first_15m_cycle_payload: blocked payload has hard_locks
- build_e2j_first_15m_cycle_payload: blocked payload has paper_decisions_created=0
- build_e2j_first_15m_cycle_payload: blocked payload has positions_created=0
- build_e2j_first_15m_cycle_payload: blocked payload has pnl_created=0
- build_e2j_first_15m_cycle_payload: blocked payload has buy_enabled=False
- build_e2j_first_15m_cycle_payload: blocked payload has sell_enabled=False
- build_e2j_first_15m_cycle_payload: blocked payload has hold_enabled=False
- build_e2j_first_15m_cycle_payload: executed with fixture adapter + all gates pass
- build_e2j_first_15m_cycle_payload: executed status is E2J_STATUS_EXECUTED
- build_e2j_first_15m_cycle_payload: executed payload has executed=True
- build_e2j_first_15m_cycle_payload: executed payload has cycle_status=SUCCEEDED
- build_e2j_first_15m_cycle_payload: executed payload has approved_token_mint
- build_e2j_first_15m_cycle_payload: executed payload has job_id (int)
- build_e2j_first_15m_cycle_payload: executed payload has handler_result
- build_e2j_first_15m_cycle_payload: executed payload has before_counts dict
- build_e2j_first_15m_cycle_payload: executed payload has after_counts dict
- build_e2j_first_15m_cycle_payload: executed payload has deltas dict
- build_e2j_first_15m_cycle_payload: scheduler_jobs delta is +1 after execution
- build_e2j_first_15m_cycle_payload: source_requests delta is +1 after execution
- build_e2j_first_15m_cycle_payload: source_responses or source_failures delta is +1
- build_e2j_first_15m_cycle_payload: paper_decisions_created is 0
- build_e2j_first_15m_cycle_payload: positions_created is 0
- build_e2j_first_15m_cycle_payload: pnl_created is 0
- build_e2j_first_15m_cycle_payload: buy_enabled=False
- build_e2j_first_15m_cycle_payload: sell_enabled=False
- build_e2j_first_15m_cycle_payload: hold_enabled=False
- build_e2j_first_15m_cycle_payload: forbidden_table_violations is empty list
- build_e2j_first_15m_cycle_payload: locks_cleared is True after execution
- build_e2j_first_15m_cycle_payload: no_running_jobs_after is True
- build_e2j_first_15m_cycle_payload: exec_error is None when succeeded
- build_e2j_first_15m_cycle_payload: payload is JSON serializable
- build_e2j_first_15m_cycle_payload: command field is printer-run-e2j-first-15m-cycle
- DB: printer_paper_decisions remains 0 after execution
- DB: printer_paper_positions remains 0 after execution
- DB: printer_paper_trade_events remains 0 after execution
- DB: printer_paper_trade_audits remains 0 after execution
- DB: printer_scheduler_jobs has 1 row after execution (SUCCEEDED)
- DB: scheduler job status is SUCCEEDED
- DB: scheduler job kind is TRACK_FAST_FIRST_15M
- DB: scheduler job lock_owner cleared after execution
- DB: printer_source_requests has 1 row after execution
- CLI: main_run_e2j_first_15m_cycle exists and is callable
- CLI: returns 0 for valid args with fixture adapter
- CLI: outputs valid JSON
- CLI: payload has command field
- CLI: blocked when --operator-approved not set
- pyproject.toml entry registered
- E2G integration: e2g_first_run_status is OPERATOR_RUN_READY in executed payload
- approved_token_mint matches token list mint
- multiple tokens in list still blocked (1 token only)
"""

import io
import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.e2j_first_15m_cycle import (
    E2J_CYCLE_JOB_KIND,
    E2J_LOCK_OWNER,
    E2J_JOB_NAME,
    E2J_STATUS_EXECUTED,
    E2J_STATUS_BLOCKED,
    _AUDIT_TABLES,
    _FORBIDDEN_DELTA_TABLES,
    _HARD_LOCKS,
    build_e2j_first_15m_cycle_payload,
)
from printer_v1.operator_cli.commands import main_run_e2j_first_15m_cycle
from printer_v1.sources.governed_execution import (
    build_fixture_source_adapter,
    FIXTURE_SUCCESS,
)


_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_MINT_2 = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
_VALID_NOTE = "Operator-approved for E2J test. Reviewed 2026-06-28."
_PAIR_ADDR = "TestPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


def _build_fixture_adapter(mint: str = _MINT_1):
    """Fixture adapter with valid normalized payload for E2M snapshot persistence."""
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_kind=FIXTURE_SUCCESS,
        fixture_payload={
            "source_name": "dexscreener",
            "request_kind": "pair_market_snapshot",
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": _PAIR_ADDR,
                    "token_mint": mint,
                    "symbol": "TEST",
                    "name": "Test Token",
                    "price_usd": 0.00042,
                    "liquidity_usd": 50000.0,
                    "volume_5m": 1000.0,
                    "volume_1h": 12000.0,
                    "volume_24h": 288000.0,
                    "txns_5m": 10,
                    "txns_1h": 120,
                    "txns_24h": 2880,
                    "fdv": 420000.0,
                    "market_cap": 380000.0,
                    "price_change_5m": 0.5,
                    "price_change_1h": 2.1,
                    "price_change_24h": -3.4,
                }
            ],
        },
    )


def _build_bad_mint_fixture_adapter():
    """Fixture adapter with wrong mint — E2M will block."""
    return build_fixture_source_adapter(
        "dexscreener",
        fixture_kind=FIXTURE_SUCCESS,
        fixture_payload={
            "source_name": "dexscreener",
            "request_kind": "pair_market_snapshot",
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": _PAIR_ADDR,
                    "token_mint": _MINT_2,
                    "symbol": "OTHER",
                    "name": "Other Token",
                    "price_usd": 0.001,
                    "liquidity_usd": 10000.0,
                }
            ],
        },
    )


class _DbTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
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

    def _build_valid_payload(self, *, operator_approved: bool = True) -> dict:
        token_file = self._write_token_file([self._valid_token_entry()])
        return build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=operator_approved,
            _adapter=_build_fixture_adapter(),
        )


# ---------------------------------------------------------------------------
# Module and constant tests
# ---------------------------------------------------------------------------

class LaneE2JImportTests(unittest.TestCase):
    def test_module_importable(self):
        import printer_v1.operator_cli.e2j_first_15m_cycle as mod
        self.assertIsNotNone(mod)

    def test_cycle_job_kind_is_track_fast_first_15m(self):
        self.assertEqual(E2J_CYCLE_JOB_KIND, "TRACK_FAST_FIRST_15M")

    def test_lock_owner_defined(self):
        self.assertIsInstance(E2J_LOCK_OWNER, str)
        self.assertGreater(len(E2J_LOCK_OWNER), 3)

    def test_job_name_defined(self):
        self.assertIsInstance(E2J_JOB_NAME, str)
        self.assertGreater(len(E2J_JOB_NAME), 3)

    def test_status_executed_defined(self):
        self.assertIsInstance(E2J_STATUS_EXECUTED, str)
        self.assertGreater(len(E2J_STATUS_EXECUTED), 5)

    def test_status_blocked_defined(self):
        self.assertIsInstance(E2J_STATUS_BLOCKED, str)
        self.assertGreater(len(E2J_STATUS_BLOCKED), 5)

    def test_audit_tables_nonempty(self):
        self.assertGreater(len(_AUDIT_TABLES), 0)

    def test_audit_tables_includes_source_requests(self):
        self.assertIn("printer_source_requests", _AUDIT_TABLES)

    def test_audit_tables_includes_scheduler_jobs(self):
        self.assertIn("printer_scheduler_jobs", _AUDIT_TABLES)

    def test_forbidden_delta_tables_nonempty(self):
        self.assertGreater(len(_FORBIDDEN_DELTA_TABLES), 0)

    def test_forbidden_delta_tables_includes_paper_decisions(self):
        self.assertIn("printer_paper_decisions", _FORBIDDEN_DELTA_TABLES)

    def test_forbidden_delta_tables_includes_paper_positions(self):
        self.assertIn("printer_paper_positions", _FORBIDDEN_DELTA_TABLES)

    def test_hard_locks_nonempty(self):
        self.assertGreater(len(_HARD_LOCKS), 0)


# ---------------------------------------------------------------------------
# Hard lock flag tests
# ---------------------------------------------------------------------------

class LaneE2JHardLockTests(unittest.TestCase):
    def test_no_buy_sell_hold_is_true(self):
        self.assertTrue(_HARD_LOCKS.get("no_buy_sell_hold"))

    def test_no_paper_decisions_is_true(self):
        self.assertTrue(_HARD_LOCKS.get("no_paper_decisions"))

    def test_no_positions_is_true(self):
        self.assertTrue(_HARD_LOCKS.get("no_positions"))

    def test_no_pnl_is_true(self):
        self.assertTrue(_HARD_LOCKS.get("no_pnl"))

    def test_no_live_trading_is_true(self):
        self.assertTrue(_HARD_LOCKS.get("no_live_trading"))

    def test_no_paid_api_is_true(self):
        self.assertTrue(_HARD_LOCKS.get("no_paid_api"))

    def test_no_generic_search_is_true(self):
        self.assertTrue(_HARD_LOCKS.get("no_generic_search"))

    def test_all_hard_locks_are_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"hard_locks[{key!r}] should be True")


# ---------------------------------------------------------------------------
# Blocked gate tests
# ---------------------------------------------------------------------------

class LaneE2JBlockedGateTests(_DbTestBase):
    def _blocked_payload(self, **kwargs) -> dict:
        defaults = dict(
            token_list_path=self._write_token_file([self._valid_token_entry()]),
            db_path=self.db_path,
            backup_proof_path=self.backup_proof_path,
            operator_approved=False,
        )
        defaults.update(kwargs)
        return build_e2j_first_15m_cycle_payload(**defaults)

    def test_blocked_when_operator_not_approved(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_when_operator_not_approved_executed_false(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertFalse(p["executed"])

    def test_blocked_when_db_path_none(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        p = build_e2j_first_15m_cycle_payload(
            token_file, None, self.backup_proof_path, operator_approved=True
        )
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_when_db_path_missing(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        p = build_e2j_first_15m_cycle_payload(
            token_file,
            pathlib.Path(self._tmp.name) / "no_such_db.sqlite3",
            self.backup_proof_path,
            operator_approved=True,
        )
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_when_backup_proof_none(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        p = build_e2j_first_15m_cycle_payload(
            token_file, self.db_path, None, operator_approved=True
        )
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_when_backup_proof_missing(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        p = build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            pathlib.Path(self._tmp.name) / "no_backup.sqlite3",
            operator_approved=True,
        )
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_when_token_list_none(self):
        p = build_e2j_first_15m_cycle_payload(
            None, self.db_path, self.backup_proof_path, operator_approved=True
        )
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_when_token_list_empty(self):
        token_file = self._write_token_file([])
        p = build_e2j_first_15m_cycle_payload(
            token_file, self.db_path, self.backup_proof_path, operator_approved=True
        )
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_when_two_tokens_in_list(self):
        token_file = self._write_token_file(
            [self._valid_token_entry(_MINT_1), self._valid_token_entry(_MINT_2)]
        )
        p = build_e2j_first_15m_cycle_payload(
            token_file, self.db_path, self.backup_proof_path, operator_approved=True
        )
        self.assertEqual(p["e2j_status"], E2J_STATUS_BLOCKED)

    def test_blocked_payload_has_hard_locks(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertIn("hard_locks", p)
        self.assertIsInstance(p["hard_locks"], dict)

    def test_blocked_payload_paper_decisions_zero(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertEqual(p["paper_decisions_created"], 0)

    def test_blocked_payload_positions_zero(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertEqual(p["positions_created"], 0)

    def test_blocked_payload_pnl_zero(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertEqual(p["pnl_created"], 0)

    def test_blocked_payload_buy_false(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertFalse(p["buy_enabled"])

    def test_blocked_payload_sell_false(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertFalse(p["sell_enabled"])

    def test_blocked_payload_hold_false(self):
        p = self._blocked_payload(operator_approved=False)
        self.assertFalse(p["hold_enabled"])


# ---------------------------------------------------------------------------
# Execution tests (fixture adapter)
# ---------------------------------------------------------------------------

class LaneE2JExecutedTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        token_file = self._write_token_file([self._valid_token_entry()])
        self.payload = build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_fixture_adapter(),
        )

    def test_status_is_executed(self):
        self.assertEqual(self.payload["e2j_status"], E2J_STATUS_EXECUTED)

    def test_executed_is_true(self):
        self.assertTrue(self.payload["executed"])

    def test_cycle_status_is_succeeded(self):
        self.assertEqual(self.payload["cycle_status"], "SUCCEEDED")

    def test_approved_token_mint_matches(self):
        self.assertEqual(self.payload["approved_token_mint"], _MINT_1)

    def test_job_id_is_int(self):
        self.assertIsInstance(self.payload["job_id"], int)

    def test_job_id_is_positive(self):
        self.assertGreater(self.payload["job_id"], 0)

    def test_handler_result_present(self):
        self.assertIn("handler_result", self.payload)
        self.assertIsInstance(self.payload["handler_result"], dict)

    def test_handler_result_executed_true(self):
        self.assertTrue(self.payload["handler_result"].get("executed"))

    def test_before_counts_present(self):
        self.assertIn("before_counts", self.payload)
        self.assertIsInstance(self.payload["before_counts"], dict)

    def test_after_counts_present(self):
        self.assertIn("after_counts", self.payload)
        self.assertIsInstance(self.payload["after_counts"], dict)

    def test_deltas_present(self):
        self.assertIn("deltas", self.payload)
        self.assertIsInstance(self.payload["deltas"], dict)

    def test_scheduler_jobs_delta_is_one(self):
        self.assertEqual(self.payload["deltas"].get("printer_scheduler_jobs"), 1)

    def test_source_requests_delta_is_one(self):
        self.assertEqual(self.payload["deltas"].get("printer_source_requests"), 1)

    def test_source_response_or_failure_delta_is_one(self):
        resp = self.payload["deltas"].get("printer_source_responses", 0)
        fail = self.payload["deltas"].get("printer_source_failures", 0)
        self.assertEqual(resp + fail, 1)

    def test_paper_decisions_created_zero(self):
        self.assertEqual(self.payload["paper_decisions_created"], 0)

    def test_positions_created_zero(self):
        self.assertEqual(self.payload["positions_created"], 0)

    def test_pnl_created_zero(self):
        self.assertEqual(self.payload["pnl_created"], 0)

    def test_buy_enabled_false(self):
        self.assertFalse(self.payload["buy_enabled"])

    def test_sell_enabled_false(self):
        self.assertFalse(self.payload["sell_enabled"])

    def test_hold_enabled_false(self):
        self.assertFalse(self.payload["hold_enabled"])

    def test_forbidden_table_violations_empty(self):
        self.assertEqual(self.payload["forbidden_table_violations"], [])

    def test_locks_cleared_true(self):
        self.assertTrue(self.payload["locks_cleared"])

    def test_no_running_jobs_after_true(self):
        self.assertTrue(self.payload["no_running_jobs_after"])

    def test_exec_error_is_none(self):
        self.assertIsNone(self.payload["exec_error"])

    def test_hard_locks_present(self):
        self.assertIn("hard_locks", self.payload)

    def test_payload_json_serializable(self):
        j = json.dumps(self.payload)
        self.assertIsInstance(j, str)
        self.assertGreater(len(j), 10)

    def test_command_field(self):
        self.assertEqual(self.payload["command"], "printer-run-e2j-first-15m-cycle")

    def test_e2g_first_run_status_is_operator_run_ready(self):
        from printer_v1.operator_cli.e2g_operator_run import OPERATOR_RUN_READY
        self.assertEqual(self.payload["e2g_first_run_status"], OPERATOR_RUN_READY)


# ---------------------------------------------------------------------------
# DB state after execution tests
# ---------------------------------------------------------------------------

class LaneE2JDbStateTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        token_file = self._write_token_file([self._valid_token_entry()])
        build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_fixture_adapter(),
        )

    def test_paper_decisions_remain_zero(self):
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_paper_positions_remain_zero(self):
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_paper_trade_events_remain_zero(self):
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)

    def test_paper_trade_audits_remain_zero(self):
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)

    def test_scheduler_jobs_has_one_row(self):
        self.assertEqual(self._count_rows("printer_scheduler_jobs"), 1)

    def test_scheduler_job_status_is_succeeded(self):
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT status FROM printer_scheduler_jobs").fetchone()
        conn.close()
        self.assertEqual(row[0], "SUCCEEDED")

    def test_scheduler_job_kind_is_track_fast_first_15m(self):
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT job_kind FROM printer_scheduler_jobs").fetchone()
        conn.close()
        self.assertEqual(row[0], "TRACK_FAST_FIRST_15M")

    def test_scheduler_job_lock_owner_cleared(self):
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT lock_owner FROM printer_scheduler_jobs").fetchone()
        conn.close()
        self.assertIsNone(row[0])

    def test_scheduler_job_locked_at_cleared(self):
        conn = sqlite3.connect(str(self.db_path))
        row = conn.execute("SELECT locked_at FROM printer_scheduler_jobs").fetchone()
        conn.close()
        self.assertIsNone(row[0])

    def test_source_requests_has_one_row(self):
        self.assertEqual(self._count_rows("printer_source_requests"), 1)

    def test_source_response_or_failure_written(self):
        resp = self._count_rows("printer_source_responses")
        fail = self._count_rows("printer_source_failures")
        self.assertEqual(resp + fail, 1)


# ---------------------------------------------------------------------------
# CLI tests
# ---------------------------------------------------------------------------

class LaneE2JCLITests(_DbTestBase):
    def test_cli_function_exists(self):
        self.assertTrue(callable(main_run_e2j_first_15m_cycle))

    def test_cli_returns_zero_with_fixture_adapter(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        ret = main_run_e2j_first_15m_cycle(
            [
                "--token-list-path", str(token_file),
                "--db-path", str(self.db_path),
                "--backup-proof-path", str(self.backup_proof_path),
                "--operator-approved",
                "--format", "json",
            ],
            _adapter=_build_fixture_adapter(),
        )
        self.assertEqual(ret, 0)

    def test_cli_outputs_valid_json(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        captured = io.StringIO()
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_run_e2j_first_15m_cycle(
                [
                    "--token-list-path", str(token_file),
                    "--db-path", str(self.db_path),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--operator-approved",
                    "--format", "json",
                ],
                _adapter=_build_fixture_adapter(),
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertIsInstance(parsed, dict)

    def test_cli_output_has_command_field(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        captured = io.StringIO()
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_run_e2j_first_15m_cycle(
                [
                    "--token-list-path", str(token_file),
                    "--db-path", str(self.db_path),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--operator-approved",
                    "--format", "json",
                ],
                _adapter=_build_fixture_adapter(),
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed.get("command"), "printer-run-e2j-first-15m-cycle")

    def test_cli_blocked_when_operator_not_approved(self):
        token_file = self._write_token_file([self._valid_token_entry()])
        captured = io.StringIO()
        import sys
        old_stdout = sys.stdout
        sys.stdout = captured
        try:
            main_run_e2j_first_15m_cycle(
                [
                    "--token-list-path", str(token_file),
                    "--db-path", str(self.db_path),
                    "--backup-proof-path", str(self.backup_proof_path),
                    "--format", "json",
                ],
                _adapter=_build_fixture_adapter(),
            )
        finally:
            sys.stdout = old_stdout
        parsed = json.loads(captured.getvalue())
        self.assertEqual(parsed.get("e2j_status"), E2J_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# pyproject.toml entry point test
# ---------------------------------------------------------------------------

class LaneE2JPyprojectTests(unittest.TestCase):
    def test_pyproject_entry_registered(self):
        toml_path = PROJECT_ROOT / "pyproject.toml"
        content = toml_path.read_text(encoding="utf-8")
        self.assertIn("printer-run-e2j-first-15m-cycle", content)

    def test_pyproject_entry_points_to_correct_function(self):
        toml_path = PROJECT_ROOT / "pyproject.toml"
        content = toml_path.read_text(encoding="utf-8")
        self.assertIn("main_run_e2j_first_15m_cycle", content)


# ---------------------------------------------------------------------------
# Token-specific / security constraint tests
# ---------------------------------------------------------------------------

class LaneE2JSecurityTests(_DbTestBase):
    def test_approved_token_mint_in_executed_payload(self):
        p = self._build_valid_payload()
        self.assertEqual(p["approved_token_mint"], _MINT_1)

    def test_approved_token_mint_not_generic_sol(self):
        p = self._build_valid_payload()
        self.assertNotIn("q=SOL", p.get("approved_token_mint", ""))

    def test_no_generic_search_lock_true(self):
        p = self._build_valid_payload()
        self.assertTrue(p["hard_locks"].get("no_generic_search"))

    def test_zero_clean_memories_is_valid(self):
        p = self._build_valid_payload()
        delta = p["deltas"].get("printer_memories", 0)
        self.assertIn(delta, (0, "unknown"), f"memories delta should be 0 or unknown, got {delta!r}")

    def test_snapshot_delta_is_one_after_clean_execution(self):
        p = self._build_valid_payload()
        # E2N: successful run with valid DexScreener payload creates exactly one snapshot.
        self.assertEqual(p["deltas"].get("printer_token_snapshots", 0), 1)

    def test_no_paper_decisions_on_execution(self):
        p = self._build_valid_payload()
        self.assertEqual(p["paper_decisions_created"], 0)

    def test_db_paper_tables_untouched(self):
        self._build_valid_payload()
        for tbl in ("printer_paper_decisions", "printer_paper_positions",
                    "printer_paper_trade_events", "printer_paper_trade_audits"):
            self.assertEqual(self._count_rows(tbl), 0, f"{tbl} should be 0")


# ---------------------------------------------------------------------------
# Lane E2N: snapshot integration into 15m cycle
# ---------------------------------------------------------------------------

class LaneE2NSnapshotIntegrationTests(_DbTestBase):
    """E2N: E2J+E2M integration — successful cycle creates one token snapshot."""

    def _run_valid(self) -> dict:
        token_file = self._write_token_file([self._valid_token_entry()])
        return build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_fixture_adapter(),
        )

    def test_successful_run_creates_one_token_snapshot(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_token_snapshots"), 1)

    def test_snapshot_persistence_status_persisted(self):
        result = self._run_valid()
        from printer_v1.operator_cli.e2m_snapshot_persistence import E2M_STATUS_PERSISTED
        self.assertEqual(result.get("snapshot_persistence_status"), E2M_STATUS_PERSISTED)

    def test_snapshot_id_in_result(self):
        result = self._run_valid()
        self.assertIsNotNone(result.get("snapshot_id"))
        self.assertIsInstance(result["snapshot_id"], int)

    def test_token_row_created(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_tokens"), 1)

    def test_pair_row_created(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_pairs"), 1)

    def test_e2j_cycle_status_still_succeeded(self):
        result = self._run_valid()
        self.assertEqual(result.get("cycle_status"), "SUCCEEDED")

    def test_e2j_status_still_executed(self):
        result = self._run_valid()
        self.assertEqual(result.get("e2j_status"), E2J_STATUS_EXECUTED)

    def test_e2j_executed_flag_true(self):
        result = self._run_valid()
        self.assertTrue(result.get("executed"))

    def test_snapshot_token_snapshots_delta_one(self):
        result = self._run_valid()
        self.assertEqual(result["deltas"].get("printer_token_snapshots"), 1)

    def test_no_memory_windows_created(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_memory_windows"), 0)

    def test_no_memories_created(self):
        before = self._count_rows("printer_memories")
        self._run_valid()
        self.assertEqual(self._count_rows("printer_memories"), before)

    def test_no_paper_decisions_created(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_no_paper_positions_created(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_paper_positions"), 0)

    def test_no_paper_trade_events_created(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_paper_trade_events"), 0)

    def test_no_paper_trade_audits_created(self):
        self._run_valid()
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), 0)

    def test_e2j_blocks_when_e2m_blocks_on_wrong_mint(self):
        """If E2M blocks (wrong mint in response), E2J must fail, not succeed."""
        token_file = self._write_token_file([self._valid_token_entry(_MINT_1)])
        result = build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_bad_mint_fixture_adapter(),
        )
        self.assertEqual(result.get("e2j_status"), E2J_STATUS_BLOCKED)
        self.assertFalse(result.get("executed"))

    def test_e2j_job_failed_when_e2m_blocks(self):
        token_file = self._write_token_file([self._valid_token_entry(_MINT_1)])
        build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_bad_mint_fixture_adapter(),
        )
        conn = sqlite3.connect(str(self.db_path))
        try:
            row = conn.execute(
                "SELECT status FROM printer_scheduler_jobs"
                " WHERE job_kind = 'TRACK_FAST_FIRST_15M' ORDER BY id DESC LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], "FAILED")

    def test_e2j_cycle_status_e2m_blocked(self):
        token_file = self._write_token_file([self._valid_token_entry(_MINT_1)])
        result = build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_bad_mint_fixture_adapter(),
        )
        self.assertEqual(result.get("cycle_status"), "E2M_BLOCKED")

    def test_e2m_blocked_creates_no_snapshot(self):
        token_file = self._write_token_file([self._valid_token_entry(_MINT_1)])
        build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_bad_mint_fixture_adapter(),
        )
        self.assertEqual(self._count_rows("printer_token_snapshots"), 0)

    def test_e2m_blocked_exec_error_mentions_e2m(self):
        token_file = self._write_token_file([self._valid_token_entry(_MINT_1)])
        result = build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_bad_mint_fixture_adapter(),
        )
        err = result.get("exec_error", "")
        self.assertIn("E2M_BLOCKED", err)

    def test_e2m_blocked_no_paper_decisions(self):
        token_file = self._write_token_file([self._valid_token_entry(_MINT_1)])
        build_e2j_first_15m_cycle_payload(
            token_file,
            self.db_path,
            self.backup_proof_path,
            operator_approved=True,
            _adapter=_build_bad_mint_fixture_adapter(),
        )
        self.assertEqual(self._count_rows("printer_paper_decisions"), 0)

    def test_snapshot_persistence_status_in_result_on_success(self):
        result = self._run_valid()
        self.assertIn("snapshot_persistence_status", result)
        self.assertNotEqual(result["snapshot_persistence_status"], "NOT_ATTEMPTED")

    def test_snapshot_persistence_status_not_attempted_when_handler_blocked(self):
        """If E2H blocks (no transport), snapshot persistence should not be attempted."""
        from unittest.mock import patch
        _TRANSPORT = "printer_v1.operator_cli.e2h_runtime_handler.check_real_source_transport_available"
        token_file = self._write_token_file([self._valid_token_entry()])
        with patch(_TRANSPORT, return_value=(False, "fixture-only transport")):
            result = build_e2j_first_15m_cycle_payload(
                token_file,
                self.db_path,
                self.backup_proof_path,
                operator_approved=True,
                _adapter=_build_fixture_adapter(),
            )
        self.assertEqual(result.get("snapshot_persistence_status"), "NOT_ATTEMPTED")
        self.assertEqual(self._count_rows("printer_token_snapshots"), 0)


if __name__ == "__main__":
    unittest.main()
