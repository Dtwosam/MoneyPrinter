import pathlib
import sqlite3
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.paper_quote.evidence import ALLOWED_CALLER, insert_paper_quote_evidence
from printer_v1.paper_quote.jupiter_fixture import (
    insert_jupiter_quote_fixture_evidence,
    normalize_jupiter_quote_fixture_payload,
)
from printer_v1.sources.contracts import NormalizedSourceResult, build_governed_source_request
from printer_v1.sources.governed_execution import (
    FIXTURE_FAILURE,
    FIXTURE_STALE,
    build_fixture_source_adapter,
    execute_source_request_with_governor,
)


def valid_fixture_payload(**overrides):
    payload = {
        "route_available": True,
        "route_plan_present": True,
        "slippage_bps": 50,
        "price_impact_bps": 40,
        "quote_captured_at": "2026-06-23T12:00:00+00:00",
        "freshness_label": "QUOTE_FRESH",
        "target_status": "TARGET_MATCH",
        "paper_only_context": True,
        "liquidity_context_label": "LIQUIDITY_CONTEXT_ACCEPTABLE",
    }
    payload.update(overrides)
    return payload


class PostRcJupiterPaperQuoteEvidenceFixtureNormalizerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.seed_core_rows()

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()
        self.tempdir.cleanup()

    def seed_core_rows(self):
        self.connection.execute(
            """
            INSERT INTO printer_tokens (
                id, token_mint, chain, symbol, name, token_status
            ) VALUES (1, 'fixture-mint', 'solana', 'FIX', 'Fixture Token', 'TRACKING')
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_pairs (
                id, token_id, pair_address, dex, pool_source
            ) VALUES (1, 1, 'fixture-pair', 'raydium', 'fixture')
            """
        )
        self.connection.execute(
            """
            INSERT INTO printer_token_snapshots (
                id,
                token_id,
                pair_id,
                captured_at,
                tracking_lane,
                snapshot_mode,
                price_usd,
                liquidity_usd,
                source_status,
                data_quality_label
            ) VALUES (
                1,
                1,
                1,
                '2026-06-23T12:00:00+00:00',
                'TRACK_NORMAL',
                'WINDOW_CLOSE',
                0.001,
                50000,
                'COMPLETE',
                'CLEAN_DATA'
            )
            """
        )
        self.connection.commit()

    def table_names(self):
        rows = self.connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
        return {row[0] for row in rows}

    def row_count(self, table_name):
        return self.connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    def execute_governed_fixture(self, payload, *, fixture_kind=None):
        request = build_governed_source_request(
            "jupiter_quote",
            "paper_quote_realism",
            request_key="fixture-jupiter-paper-quote",
            tracking_priority=1,
            payload={"quote_direction": "ENTRY"},
        )
        adapter = build_fixture_source_adapter(
            "jupiter_quote",
            fixture_kind=fixture_kind or "fixture_success",
            fixture_payload=payload,
        )
        return execute_source_request_with_governor(self.connection, request, adapter)

    def insert_from_governed_result(self, governed_result, *, quote_direction="ENTRY"):
        return insert_jupiter_quote_fixture_evidence(
            self.connection,
            governed_result.normalized_result,
            request_record=governed_result.request_record,
            response_record=governed_result.response_record,
            failure_record=governed_result.failure_record,
            quote_direction=quote_direction,
            token_id=1,
            pair_id=1,
            snapshot_id=1,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=ALLOWED_CALLER,
        )

    def test_valid_entry_fixture_creates_guarded_paper_quote_evidence_row(self):
        governed_result = self.execute_governed_fixture(valid_fixture_payload())
        result = self.insert_from_governed_result(governed_result, quote_direction="ENTRY")

        self.assertTrue(result.inserted)
        self.assertTrue(result.clean_eligible)
        self.assertEqual(result.source_trace_status, "SOURCE_TRACE_PRESENT")
        self.assertEqual(set(result.downstream_unlocks.values()), {False})

        row = self.connection.execute(
            "SELECT * FROM printer_paper_quote_evidence WHERE id = ?",
            (result.evidence_id,),
        ).fetchone()
        self.assertEqual(row["source_name"], "jupiter_quote")
        self.assertEqual(row["source_request_id"], governed_result.request_record.id)
        self.assertEqual(row["source_response_id"], governed_result.response_record.id)
        self.assertIsNone(row["source_failure_id"])
        self.assertEqual(row["entry_realism_label"], "ENTRY_ROUTE_AVAILABLE")
        self.assertEqual(row["exit_realism_label"], "EXIT_UNKNOWN")
        self.assertEqual(row["quote_context_label"], "QUOTE_ROUTE_AVAILABLE")

    def test_valid_exit_fixture_creates_exit_realism_evidence(self):
        governed_result = self.execute_governed_fixture(valid_fixture_payload())
        result = self.insert_from_governed_result(governed_result, quote_direction="EXIT")

        self.assertTrue(result.inserted)
        self.assertTrue(result.clean_eligible)
        row = self.connection.execute(
            "SELECT * FROM printer_paper_quote_evidence WHERE id = ?",
            (result.evidence_id,),
        ).fetchone()
        self.assertEqual(row["entry_realism_label"], "ENTRY_UNKNOWN")
        self.assertEqual(row["exit_realism_label"], "EXIT_ROUTE_AVAILABLE")

    def test_missing_entry_and_exit_routes_are_audit_only_not_clean(self):
        for direction in ("ENTRY", "EXIT"):
            with self.subTest(direction=direction):
                governed_result = self.execute_governed_fixture(
                    valid_fixture_payload(route_available=False, route_plan_present=False)
                )
                result = self.insert_from_governed_result(
                    governed_result,
                    quote_direction=direction,
                )

                self.assertTrue(result.inserted)
                self.assertFalse(result.clean_eligible)
                row = self.connection.execute(
                    "SELECT * FROM printer_paper_quote_evidence WHERE id = ?",
                    (result.evidence_id,),
                ).fetchone()
                self.assertEqual(row["route_available_label"], "ROUTE_UNAVAILABLE")
                self.assertEqual(row["quote_failure_label"], "NO_ROUTE_AVAILABLE")

    def test_stale_and_failed_source_results_remain_audit_only(self):
        stale_result = self.execute_governed_fixture(
            valid_fixture_payload(),
            fixture_kind=FIXTURE_STALE,
        )
        stale_insert = self.insert_from_governed_result(stale_result)
        self.assertTrue(stale_insert.inserted)
        self.assertFalse(stale_insert.clean_eligible)
        stale_row = self.connection.execute(
            "SELECT * FROM printer_paper_quote_evidence WHERE id = ?",
            (stale_insert.evidence_id,),
        ).fetchone()
        self.assertEqual(stale_row["freshness_label"], "QUOTE_STALE")
        self.assertEqual(stale_row["quote_context_label"], "QUOTE_STALE")

        failure_result = self.execute_governed_fixture({}, fixture_kind=FIXTURE_FAILURE)
        failed_insert = self.insert_from_governed_result(failure_result)
        self.assertTrue(failed_insert.inserted)
        self.assertFalse(failed_insert.clean_eligible)
        failed_row = self.connection.execute(
            "SELECT * FROM printer_paper_quote_evidence WHERE id = ?",
            (failed_insert.evidence_id,),
        ).fetchone()
        self.assertIsNone(failed_row["source_response_id"])
        self.assertEqual(failed_row["source_failure_id"], failure_result.failure_record.id)
        self.assertEqual(failed_row["quote_context_label"], "QUOTE_FAILED")

    def test_partial_placeholder_quote_evidence_is_blocked_from_clean_eligibility(self):
        governed_result = self.execute_governed_fixture(valid_fixture_payload())
        evidence = normalize_jupiter_quote_fixture_payload(
            {"route_plan_present": True, "quote_captured_at": "2026-06-23T12:00:00+00:00"},
            quote_direction="ENTRY",
            token_id=1,
            pair_id=1,
            snapshot_id=1,
            source_request_id=governed_result.request_record.id,
            source_response_id=governed_result.response_record.id,
            source_status="PARTIAL",
            data_quality_label="ACCEPTABLE_PARTIAL_DATA",
        )
        result = insert_paper_quote_evidence(
            self.connection,
            evidence,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=ALLOWED_CALLER,
        )

        self.assertTrue(result.inserted)
        self.assertFalse(result.clean_eligible)
        row = self.connection.execute(
            "SELECT * FROM printer_paper_quote_evidence WHERE id = ?",
            (result.evidence_id,),
        ).fetchone()
        self.assertEqual(row["quote_context_label"], "QUOTE_UNKNOWN")
        self.assertEqual(row["route_available_label"], "ROUTE_UNKNOWN")

    def test_target_mismatch_and_non_paper_context_are_rejected_by_guarded_helper(self):
        for payload, expected_reason in (
            (
                valid_fixture_payload(target_status="TARGET_MISMATCH"),
                "TARGET_MISMATCH",
            ),
            (
                valid_fixture_payload(paper_only_context=False),
                "PAPER_ONLY_CONTEXT_REQUIRED",
            ),
        ):
            with self.subTest(expected_reason=expected_reason):
                evidence = normalize_jupiter_quote_fixture_payload(
                    payload,
                    quote_direction="ENTRY",
                    token_id=1,
                    pair_id=1,
                    snapshot_id=1,
                    source_request_id=1,
                    source_response_id=1,
                )
                result = insert_paper_quote_evidence(
                    self.connection,
                    evidence,
                    scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                    operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                    caller=ALLOWED_CALLER,
                )
                self.assertFalse(result.inserted)
                self.assertIn(expected_reason, result.rejection_reasons)

    def test_direct_engine_callers_cannot_insert_normalized_quote_evidence(self):
        evidence = normalize_jupiter_quote_fixture_payload(
            valid_fixture_payload(),
            quote_direction="ENTRY",
            token_id=1,
            pair_id=1,
            snapshot_id=1,
            source_request_id=1,
            source_response_id=1,
        )
        for caller in (
            "memory_engine",
            "retrieval_engine",
            "paper_decision_engine",
            "paper_position_engine",
            "pnl_engine",
        ):
            with self.subTest(caller=caller):
                result = insert_paper_quote_evidence(
                    self.connection,
                    evidence,
                    scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                    operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                    caller=caller,
                )
                self.assertFalse(result.inserted)
                self.assertIn("DIRECT_CALLER_FORBIDDEN", result.rejection_reasons)

    def test_normalizer_has_no_live_or_adapter_capability_terms(self):
        module_text = (
            PROJECT_ROOT / "src" / "printer_v1" / "paper_quote" / "jupiter_fixture.py"
        ).read_text(encoding="utf-8")
        forbidden_terms = (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "os.environ",
            "API_KEY",
            "private_key",
            "signed_tx",
            "execute_trade",
            "transaction_signature",
            "tx_signature",
            "confidence_score",
            "buy_score",
            "rank_score",
        )
        for term in forbidden_terms:
            with self.subTest(term=term):
                self.assertNotIn(term, module_text)

    def test_quote_evidence_creates_no_memory_retrieval_paper_position_or_pnl_rows(self):
        before_counts = {
            table: self.row_count(table)
            for table in (
                "printer_memory_windows",
                "printer_memory_retrieval_matches",
                "printer_paper_decisions",
                "printer_paper_positions",
                "printer_paper_trade_events",
                "printer_paper_pl_calculations",
            )
            if table in self.table_names()
        }
        governed_result = self.execute_governed_fixture(valid_fixture_payload())
        result = self.insert_from_governed_result(governed_result)

        self.assertTrue(result.inserted)
        self.assertEqual(set(result.downstream_unlocks.values()), {False})
        for table, before in before_counts.items():
            with self.subTest(table=table):
                self.assertEqual(self.row_count(table), before)

    def test_persistent_operator_db_remains_untouched(self):
        persistent_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        before_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None

        governed_result = self.execute_governed_fixture(valid_fixture_payload())
        result = self.insert_from_governed_result(governed_result)

        after_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None
        self.assertTrue(result.inserted)
        self.assertEqual(before_mtime, after_mtime)

    def test_non_jupiter_source_request_is_rejected(self):
        bad_result = NormalizedSourceResult(
            source_name="dexscreener",
            request_kind="token_market_snapshot",
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            normalized_payload=valid_fixture_payload(),
        )
        request = build_governed_source_request("dexscreener", "token_market_snapshot")
        governed_result = execute_source_request_with_governor(
            self.connection,
            request,
            build_fixture_source_adapter("dexscreener", fixture_payload={}),
        )
        with self.assertRaises(ValueError):
            insert_jupiter_quote_fixture_evidence(
                self.connection,
                bad_result,
                request_record=governed_result.request_record,
                response_record=governed_result.response_record,
                quote_direction="ENTRY",
                token_id=1,
                pair_id=1,
                snapshot_id=1,
                scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            )


if __name__ == "__main__":
    unittest.main()
