"""
Post-Lane 10 Lane E2M -- Snapshot Persistence Boundary

Tests prove:
- clean DexScreener response creates exactly one snapshot row
- second call with same source_response_id is idempotent (DUPLICATE, no new row)
- dirty/FAILED/non-CLEAN_DATA response is blocked
- wrong token_mint is blocked
- non-solana chain is blocked
- generic-search request_kind (token_discovery) is blocked
- missing normalized_payload_json is blocked
- missing pairs list is blocked
- no paper decisions created
- no positions/PnL created
- no memory or memory_window rows created
- token row is upserted (created once on first call)
- pair row is upserted (created once on first call)
- snapshot_id returned on success
- hard_locks all True
- BLOCKED when source_response not found
- BLOCKED when STALE source_status
- BLOCKED when DIRTY_DATA quality label
- BLOCKED when PARTIAL source_status
- pair selection picks highest-liquidity Solana pair for approved mint
- pair selection ignores non-solana pairs even if matching mint
"""

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
from printer_v1.operator_cli.e2m_snapshot_persistence import (
    E2M_REQUEST_KIND,
    E2M_REQUIRED_CHAIN,
    E2M_REQUIRED_QUALITY,
    E2M_REQUIRED_SOURCE_STATUS,
    E2M_SOURCE_NAME,
    E2M_STATUS_BLOCKED,
    E2M_STATUS_DUPLICATE,
    E2M_STATUS_PERSISTED,
    _HARD_LOCKS,
    persist_snapshot_from_source_response,
)


_MINT_1 = "9cRCn9rGT8V2imeM2BaKs13yhMEais3ruM3rPvTGpump"
_MINT_2 = "4k3Dyjzvzp8eMZWUXbBCjEvwSkkk59S5iCNLY3QrkX6R"
_PAIR_1 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAApair1"
_PAIR_2 = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAApair2"


def _clean_pairs_payload(
    mint: str = _MINT_1,
    pair_address: str = _PAIR_1,
    chain: str = "solana",
    liquidity_usd: float = 50000.0,
    price_usd: float = 0.00042,
) -> dict:
    return {
        "source_name": "dexscreener",
        "request_kind": "pair_market_snapshot",
        "pairs": [
            {
                "chain": chain,
                "pair_address": pair_address,
                "token_mint": mint,
                "symbol": "TEST",
                "name": "Test Token",
                "price_usd": price_usd,
                "liquidity_usd": liquidity_usd,
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
    }


class _DbTestBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(str(self.db_path))
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0
        finally:
            conn.close()

    def _insert_source_request(
        self,
        conn: sqlite3.Connection,
        source_name: str = "dexscreener",
        request_kind: str = "pair_market_snapshot",
        source_status: str = "COMPLETE",
        data_quality_label: str = "CLEAN_DATA",
    ) -> int:
        cursor = conn.execute(
            "INSERT INTO printer_source_requests"
            " (source_name, request_kind, requested_at, source_status, data_quality_label)"
            " VALUES (?, ?, datetime('now'), ?, ?)",
            (source_name, request_kind, source_status, data_quality_label),
        )
        return int(cursor.lastrowid)

    def _insert_source_response(
        self,
        conn: sqlite3.Connection,
        source_request_id: int,
        source_name: str = "dexscreener",
        source_status: str = "COMPLETE",
        data_quality_label: str = "CLEAN_DATA",
        payload: dict | None = None,
    ) -> int:
        if payload is None:
            payload = _clean_pairs_payload()
        cursor = conn.execute(
            "INSERT INTO printer_source_responses"
            " (source_request_id, source_name, received_at, source_status,"
            "  data_quality_label, normalized_payload_json)"
            " VALUES (?, ?, datetime('now'), ?, ?, ?)",
            (
                source_request_id,
                source_name,
                source_status,
                data_quality_label,
                json.dumps(payload),
            ),
        )
        return int(cursor.lastrowid)

    def _make_clean_response(
        self,
        conn: sqlite3.Connection,
        mint: str = _MINT_1,
        pair_address: str = _PAIR_1,
        chain: str = "solana",
        liquidity_usd: float = 50000.0,
    ) -> tuple[int, int]:
        """Return (source_request_id, source_response_id) for a clean response."""
        req_id = self._insert_source_request(conn)
        payload = _clean_pairs_payload(
            mint=mint, pair_address=pair_address, chain=chain, liquidity_usd=liquidity_usd
        )
        resp_id = self._insert_source_response(conn, req_id, payload=payload)
        conn.commit()
        return req_id, resp_id


# ---------------------------------------------------------------------------
# Import and constants
# ---------------------------------------------------------------------------

class LaneE2MImportTests(unittest.TestCase):
    def test_module_imports_cleanly(self):
        from printer_v1.operator_cli import e2m_snapshot_persistence
        self.assertIsNotNone(e2m_snapshot_persistence)

    def test_status_constants_defined(self):
        self.assertEqual(E2M_STATUS_PERSISTED, "E2M_SNAPSHOT_PERSISTED")
        self.assertEqual(E2M_STATUS_DUPLICATE, "E2M_SNAPSHOT_DUPLICATE")
        self.assertEqual(E2M_STATUS_BLOCKED, "E2M_SNAPSHOT_BLOCKED")

    def test_source_name_constant(self):
        self.assertEqual(E2M_SOURCE_NAME, "dexscreener")

    def test_request_kind_constant(self):
        self.assertEqual(E2M_REQUEST_KIND, "pair_market_snapshot")

    def test_required_chain_constant(self):
        self.assertEqual(E2M_REQUIRED_CHAIN, "solana")

    def test_required_source_status_constant(self):
        self.assertEqual(E2M_REQUIRED_SOURCE_STATUS, "COMPLETE")

    def test_required_quality_constant(self):
        self.assertEqual(E2M_REQUIRED_QUALITY, "CLEAN_DATA")

    def test_hard_locks_all_true(self):
        for key, val in _HARD_LOCKS.items():
            self.assertTrue(val, f"hard lock {key!r} must be True")

    def test_hard_locks_has_no_buy_sell_hold(self):
        self.assertIn("no_buy_sell_hold", _HARD_LOCKS)

    def test_hard_locks_has_no_paper_decisions(self):
        self.assertIn("no_paper_decisions", _HARD_LOCKS)

    def test_hard_locks_has_no_memory_creation(self):
        self.assertIn("no_memory_creation", _HARD_LOCKS)

    def test_hard_locks_has_no_generic_search(self):
        self.assertIn("no_generic_search", _HARD_LOCKS)


# ---------------------------------------------------------------------------
# Happy path: clean response creates snapshot
# ---------------------------------------------------------------------------

class LaneE2MHappyPathTests(_DbTestBase):
    def _run(self, mint: str = _MINT_1) -> dict:
        conn = self._connect()
        try:
            req_id, resp_id = self._make_clean_response(conn, mint=mint)
            result = persist_snapshot_from_source_response(conn, resp_id, mint)
            conn.commit()
            return result
        finally:
            conn.close()

    def test_status_is_persisted(self):
        result = self._run()
        self.assertEqual(result["e2m_status"], E2M_STATUS_PERSISTED)

    def test_persisted_flag_true(self):
        result = self._run()
        self.assertTrue(result["persisted"])

    def test_snapshot_id_returned(self):
        result = self._run()
        self.assertIsNotNone(result.get("snapshot_id"))
        self.assertIsInstance(result["snapshot_id"], int)

    def test_token_id_returned(self):
        result = self._run()
        self.assertIsNotNone(result.get("token_id"))
        self.assertIsInstance(result["token_id"], int)

    def test_pair_id_returned(self):
        result = self._run()
        self.assertIsNotNone(result.get("pair_id"))
        self.assertIsInstance(result["pair_id"], int)

    def test_exactly_one_snapshot_row(self):
        self._run()
        self.assertEqual(self._count_rows("printer_token_snapshots"), 1)

    def test_exactly_one_token_row(self):
        self._run()
        self.assertEqual(self._count_rows("printer_tokens"), 1)

    def test_exactly_one_pair_row(self):
        self._run()
        self.assertEqual(self._count_rows("printer_pairs"), 1)

    def test_token_mint_persisted_matches_approved(self):
        result = self._run()
        self.assertEqual(result["token_mint_persisted"].lower(), _MINT_1.lower())

    def test_pair_address_persisted_matches_expected(self):
        result = self._run()
        self.assertEqual(result["pair_address_persisted"], _PAIR_1)

    def test_source_request_id_in_result(self):
        result = self._run()
        self.assertIsInstance(result.get("source_request_id"), int)

    def test_source_response_id_in_result(self):
        result = self._run()
        self.assertIsInstance(result.get("source_response_id"), int)

    def test_hard_locks_all_true_in_result(self):
        result = self._run()
        for key, val in result.get("hard_locks", {}).items():
            self.assertTrue(val, f"hard lock {key!r} must be True in result")

    def test_no_paper_decisions_in_result(self):
        result = self._run()
        self.assertEqual(result.get("paper_decisions_created"), 0)

    def test_no_positions_in_result(self):
        result = self._run()
        self.assertEqual(result.get("positions_created"), 0)

    def test_no_pnl_in_result(self):
        result = self._run()
        self.assertEqual(result.get("pnl_created"), 0)

    def test_no_memory_in_result(self):
        result = self._run()
        self.assertEqual(result.get("memory_created"), 0)

    def test_no_memory_windows_in_result(self):
        result = self._run()
        self.assertEqual(result.get("memory_windows_created"), 0)


# ---------------------------------------------------------------------------
# Idempotency: second call must be duplicate
# ---------------------------------------------------------------------------

class LaneE2MIdempotencyTests(_DbTestBase):
    def test_second_call_returns_duplicate_status(self):
        conn = self._connect()
        try:
            req_id, resp_id = self._make_clean_response(conn)
            persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
            result2 = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(result2["e2m_status"], E2M_STATUS_DUPLICATE)

    def test_second_call_does_not_insert_new_row(self):
        conn = self._connect()
        try:
            req_id, resp_id = self._make_clean_response(conn)
            persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
            persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(self._count_rows("printer_token_snapshots"), 1)

    def test_second_call_returns_existing_snapshot_id(self):
        conn = self._connect()
        try:
            req_id, resp_id = self._make_clean_response(conn)
            r1 = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
            r2 = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(r2.get("existing_snapshot_id"), r1.get("snapshot_id"))

    def test_second_call_persisted_flag_false(self):
        conn = self._connect()
        try:
            req_id, resp_id = self._make_clean_response(conn)
            persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
            r2 = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
        finally:
            conn.close()
        self.assertFalse(r2.get("persisted"))

    def test_different_response_id_creates_second_snapshot(self):
        conn = self._connect()
        try:
            req_id1, resp_id1 = self._make_clean_response(conn)
            req_id2, resp_id2 = self._make_clean_response(conn, pair_address=_PAIR_2)
            persist_snapshot_from_source_response(conn, resp_id1, _MINT_1)
            conn.commit()
            r2 = persist_snapshot_from_source_response(conn, resp_id2, _MINT_1)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(r2["e2m_status"], E2M_STATUS_PERSISTED)
        self.assertEqual(self._count_rows("printer_token_snapshots"), 2)


# ---------------------------------------------------------------------------
# Blocked: invalid source metadata
# ---------------------------------------------------------------------------

class LaneE2MBlockedSourceMetadataTests(_DbTestBase):
    def test_blocked_when_response_not_found(self):
        conn = self._connect()
        try:
            result = persist_snapshot_from_source_response(conn, 99999, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)
        self.assertFalse(result["persisted"])

    def test_blocked_when_source_name_not_dexscreener(self):
        conn = self._connect()
        try:
            req_id = self._insert_source_request(conn, source_name="coingecko")
            resp_id = self._insert_source_response(conn, req_id, source_name="coingecko")
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)
        reasons = result.get("blocked_reasons", [])
        self.assertTrue(any("source_name" in r for r in reasons))

    def test_blocked_when_source_status_failed(self):
        conn = self._connect()
        try:
            req_id = self._insert_source_request(
                conn, source_status="FAILED", data_quality_label="MISSING_CRITICAL_DATA"
            )
            resp_id = self._insert_source_response(
                conn, req_id,
                source_status="FAILED",
                data_quality_label="MISSING_CRITICAL_DATA",
            )
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)
        reasons = result.get("blocked_reasons", [])
        self.assertTrue(any("source_status" in r for r in reasons))

    def test_blocked_when_source_status_stale(self):
        conn = self._connect()
        try:
            req_id = self._insert_source_request(
                conn, source_status="STALE", data_quality_label="STALE_DATA"
            )
            resp_id = self._insert_source_response(
                conn, req_id, source_status="STALE", data_quality_label="STALE_DATA"
            )
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_blocked_when_data_quality_dirty(self):
        conn = self._connect()
        try:
            req_id = self._insert_source_request(
                conn, source_status="COMPLETE", data_quality_label="DIRTY_DATA"
            )
            resp_id = self._insert_source_response(
                conn, req_id, source_status="COMPLETE", data_quality_label="DIRTY_DATA"
            )
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)
        reasons = result.get("blocked_reasons", [])
        self.assertTrue(any("data_quality_label" in r for r in reasons))

    def test_blocked_when_data_quality_partial(self):
        conn = self._connect()
        try:
            req_id = self._insert_source_request(
                conn, source_status="PARTIAL", data_quality_label="ACCEPTABLE_PARTIAL_DATA"
            )
            resp_id = self._insert_source_response(
                conn, req_id,
                source_status="PARTIAL",
                data_quality_label="ACCEPTABLE_PARTIAL_DATA",
            )
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_blocked_when_request_kind_is_token_discovery(self):
        """Generic search request_kind (token_discovery) must be blocked."""
        conn = self._connect()
        try:
            req_id = self._insert_source_request(conn, request_kind="token_discovery")
            resp_id = self._insert_source_response(conn, req_id)
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)
        reasons = result.get("blocked_reasons", [])
        self.assertTrue(any("request_kind" in r for r in reasons))


# ---------------------------------------------------------------------------
# Blocked: invalid payload content
# ---------------------------------------------------------------------------

class LaneE2MBlockedPayloadTests(_DbTestBase):
    def _run_with_payload(self, payload_json: str | None, mint: str = _MINT_1) -> dict:
        conn = self._connect()
        try:
            req_id = self._insert_source_request(conn)
            conn.execute(
                "INSERT INTO printer_source_responses"
                " (source_request_id, source_name, received_at, source_status,"
                "  data_quality_label, normalized_payload_json)"
                " VALUES (?, 'dexscreener', datetime('now'), 'COMPLETE', 'CLEAN_DATA', ?)",
                (req_id, payload_json),
            )
            conn.commit()
            resp_id = int(conn.execute(
                "SELECT id FROM printer_source_responses ORDER BY id DESC LIMIT 1"
            ).fetchone()[0])
            result = persist_snapshot_from_source_response(conn, resp_id, mint)
            conn.commit()
            return result
        finally:
            conn.close()

    def test_blocked_when_payload_json_null(self):
        result = self._run_with_payload(None)
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_blocked_when_payload_json_invalid(self):
        result = self._run_with_payload("not-json")
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_blocked_when_pairs_list_missing(self):
        result = self._run_with_payload(json.dumps({"source_name": "dexscreener"}))
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_blocked_when_pairs_list_empty(self):
        result = self._run_with_payload(json.dumps({"pairs": []}))
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_blocked_when_wrong_token_mint(self):
        payload = _clean_pairs_payload(mint=_MINT_2)
        result = self._run_with_payload(json.dumps(payload), mint=_MINT_1)
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)
        reasons = result.get("blocked_reasons", [])
        self.assertTrue(any("Solana pair" in r or "mint" in r for r in reasons))

    def test_blocked_when_chain_not_solana(self):
        payload = _clean_pairs_payload(chain="ethereum")
        result = self._run_with_payload(json.dumps(payload), mint=_MINT_1)
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_blocked_when_pair_address_missing(self):
        payload = {
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": None,
                    "token_mint": _MINT_1,
                    "price_usd": 0.001,
                    "liquidity_usd": 10000.0,
                }
            ]
        }
        result = self._run_with_payload(json.dumps(payload), mint=_MINT_1)
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# No forbidden table mutations
# ---------------------------------------------------------------------------

class LaneE2MForbiddenTableTests(_DbTestBase):
    def _run_success(self) -> None:
        conn = self._connect()
        try:
            req_id, resp_id = self._make_clean_response(conn)
            persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
        finally:
            conn.close()

    def test_no_paper_decisions_written(self):
        before = self._count_rows("printer_paper_decisions")
        self._run_success()
        self.assertEqual(self._count_rows("printer_paper_decisions"), before)

    def test_no_paper_positions_written(self):
        before = self._count_rows("printer_paper_positions")
        self._run_success()
        self.assertEqual(self._count_rows("printer_paper_positions"), before)

    def test_no_paper_trade_events_written(self):
        before = self._count_rows("printer_paper_trade_events")
        self._run_success()
        self.assertEqual(self._count_rows("printer_paper_trade_events"), before)

    def test_no_paper_trade_audits_written(self):
        before = self._count_rows("printer_paper_trade_audits")
        self._run_success()
        self.assertEqual(self._count_rows("printer_paper_trade_audits"), before)

    def test_no_memory_rows_written(self):
        before = self._count_rows("printer_memories") if self._count_rows("printer_memories") >= 0 else 0
        self._run_success()
        self.assertEqual(self._count_rows("printer_memories"), before)

    def test_no_memory_windows_written(self):
        before = self._count_rows("printer_memory_windows")
        self._run_success()
        self.assertEqual(self._count_rows("printer_memory_windows"), before)

    def test_no_source_requests_written(self):
        self._run_success()
        self.assertEqual(self._count_rows("printer_source_requests"), 1)

    def test_no_source_responses_written(self):
        self._run_success()
        self.assertEqual(self._count_rows("printer_source_responses"), 1)


# ---------------------------------------------------------------------------
# Pair selection logic
# ---------------------------------------------------------------------------

class LaneE2MPairSelectionTests(_DbTestBase):
    def test_picks_highest_liquidity_pair_for_approved_mint(self):
        payload = {
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": "low_liq_pair",
                    "token_mint": _MINT_1,
                    "symbol": "T",
                    "name": "Test",
                    "price_usd": 0.001,
                    "liquidity_usd": 5000.0,
                    "volume_5m": None,
                    "volume_1h": None,
                    "volume_24h": None,
                    "txns_5m": None,
                    "txns_1h": None,
                    "txns_24h": None,
                    "fdv": None,
                    "market_cap": None,
                    "price_change_5m": None,
                    "price_change_1h": None,
                    "price_change_24h": None,
                },
                {
                    "chain": "solana",
                    "pair_address": "high_liq_pair",
                    "token_mint": _MINT_1,
                    "symbol": "T",
                    "name": "Test",
                    "price_usd": 0.001,
                    "liquidity_usd": 100000.0,
                    "volume_5m": None,
                    "volume_1h": None,
                    "volume_24h": None,
                    "txns_5m": None,
                    "txns_1h": None,
                    "txns_24h": None,
                    "fdv": None,
                    "market_cap": None,
                    "price_change_5m": None,
                    "price_change_1h": None,
                    "price_change_24h": None,
                },
            ]
        }
        conn = self._connect()
        try:
            req_id = self._insert_source_request(conn)
            resp_id = self._insert_source_response(conn, req_id, payload=payload)
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_PERSISTED)
        self.assertEqual(result["pair_address_persisted"], "high_liq_pair")

    def test_ignores_non_solana_pair_matching_mint(self):
        payload = {
            "pairs": [
                {
                    "chain": "ethereum",
                    "pair_address": "eth_pair",
                    "token_mint": _MINT_1,
                    "symbol": "T",
                    "name": "Test",
                    "price_usd": 0.001,
                    "liquidity_usd": 999999.0,
                    "volume_5m": None,
                    "volume_1h": None,
                    "volume_24h": None,
                    "txns_5m": None,
                    "txns_1h": None,
                    "txns_24h": None,
                    "fdv": None,
                    "market_cap": None,
                    "price_change_5m": None,
                    "price_change_1h": None,
                    "price_change_24h": None,
                },
            ]
        }
        conn = self._connect()
        try:
            req_id = self._insert_source_request(conn)
            resp_id = self._insert_source_response(conn, req_id, payload=payload)
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)

    def test_ignores_solana_pair_for_wrong_mint(self):
        payload = {
            "pairs": [
                {
                    "chain": "solana",
                    "pair_address": _PAIR_1,
                    "token_mint": _MINT_2,
                    "symbol": "T",
                    "name": "Test",
                    "price_usd": 0.001,
                    "liquidity_usd": 50000.0,
                    "volume_5m": None,
                    "volume_1h": None,
                    "volume_24h": None,
                    "txns_5m": None,
                    "txns_1h": None,
                    "txns_24h": None,
                    "fdv": None,
                    "market_cap": None,
                    "price_change_5m": None,
                    "price_change_1h": None,
                    "price_change_24h": None,
                },
            ]
        }
        conn = self._connect()
        try:
            req_id = self._insert_source_request(conn)
            resp_id = self._insert_source_response(conn, req_id, payload=payload)
            conn.commit()
            result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
        finally:
            conn.close()
        self.assertEqual(result["e2m_status"], E2M_STATUS_BLOCKED)


# ---------------------------------------------------------------------------
# DB state after successful persist
# ---------------------------------------------------------------------------

class LaneE2MDbStateTests(_DbTestBase):
    def setUp(self):
        super().setUp()
        conn = self._connect()
        try:
            req_id, resp_id = self._make_clean_response(conn)
            self._result = persist_snapshot_from_source_response(conn, resp_id, _MINT_1)
            conn.commit()
        finally:
            conn.close()

    def test_printer_tokens_has_one_row(self):
        self.assertEqual(self._count_rows("printer_tokens"), 1)

    def test_printer_pairs_has_one_row(self):
        self.assertEqual(self._count_rows("printer_pairs"), 1)

    def test_printer_token_snapshots_has_one_row(self):
        self.assertEqual(self._count_rows("printer_token_snapshots"), 1)

    def test_snapshot_has_correct_source_response_id(self):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT normalized_snapshot_payload_json"
                " FROM printer_token_snapshots LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        payload = json.loads(row["normalized_snapshot_payload_json"])
        self.assertEqual(payload["source_response_id"], self._result["source_response_id"])

    def test_snapshot_source_status_is_complete(self):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT source_status FROM printer_token_snapshots LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["source_status"], "COMPLETE")

    def test_snapshot_data_quality_is_clean(self):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT data_quality_label FROM printer_token_snapshots LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["data_quality_label"], "CLEAN_DATA")

    def test_snapshot_tracking_lane_is_track_fast(self):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT tracking_lane FROM printer_token_snapshots LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["tracking_lane"], "TRACK_FAST")

    def test_token_mint_matches_approved(self):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT token_mint FROM printer_tokens LIMIT 1"
            ).fetchone()
        finally:
            conn.close()
        self.assertEqual(row["token_mint"].lower(), _MINT_1.lower())
