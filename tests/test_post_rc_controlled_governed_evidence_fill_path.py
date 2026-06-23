import pathlib
import sqlite3
import sys
import tempfile
import unittest


PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.evidence_fill.controlled import (
    ControlledEvidenceFillTarget,
    fill_controlled_governed_evidence,
)
from printer_v1.paper_quote.evidence import ALLOWED_CALLER as QUOTE_ALLOWED_CALLER
from printer_v1.paper_quote.evidence import insert_paper_quote_evidence
from printer_v1.paper_quote.jupiter_fixture import normalize_jupiter_quote_fixture_payload
from printer_v1.safety.evidence import ALLOWED_CALLER as SAFETY_ALLOWED_CALLER
from printer_v1.safety.evidence import insert_solana_safety_evidence
from printer_v1.safety.solana_rpc_fixture import normalize_solana_rpc_safety_fixture_payload


def valid_safety_payload(**overrides):
    payload = {
        "captured_at": "2026-06-23T12:00:00+00:00",
        "mint_account": {
            "mint_authority": None,
            "freeze_authority": None,
            "token_program": "spl_token",
        },
        "metadata": {"mutable": False},
        "supply": {"supply": "1000000000"},
        "holders": {
            "top_holder_percent": 4.5,
            "top_10_holder_percent": 32.0,
        },
        "liquidity": {"lock_or_burn_status": "confirmed"},
        "risk_flags": [],
        "target_status": "TARGET_MATCH",
        "freshness_label": "SAFETY_EVIDENCE_FRESH",
    }
    payload.update(overrides)
    return payload


def valid_quote_payload(**overrides):
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


class PostRcControlledGovernedEvidenceFillPathTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.seed_core_rows()
        self.target = ControlledEvidenceFillTarget(token_id=1, pair_id=1, snapshot_id=1)

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

    def downstream_counts(self):
        tables = (
            "printer_memory_windows",
            "printer_memory_fingerprints",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_pl_calculations",
        )
        return {table: self.row_count(table) for table in tables if table in self.table_names()}

    def test_dry_run_reports_intended_safety_and_quote_inserts_but_inserts_zero_rows(self):
        result = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload=valid_safety_payload(),
            entry_quote_payload=valid_quote_payload(),
            exit_quote_payload=valid_quote_payload(),
            dry_run=True,
        )

        self.assertTrue(result.dry_run)
        self.assertEqual(len(result.item_results), 3)
        self.assertEqual(result.safety_evidence_inserted, 0)
        self.assertEqual(result.quote_evidence_inserted, 0)
        self.assertEqual(self.row_count("printer_source_requests"), 0)
        self.assertEqual(self.row_count("printer_solana_safety_evidence"), 0)
        self.assertEqual(self.row_count("printer_paper_quote_evidence"), 0)
        self.assertTrue(
            all(item.audit_status.startswith("DRY_RUN_WOULD_INSERT") for item in result.item_results)
        )

    def test_controlled_fill_inserts_valid_safety_and_quote_through_guarded_helpers(self):
        result = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload=valid_safety_payload(),
            entry_quote_payload=valid_quote_payload(),
            exit_quote_payload=valid_quote_payload(),
        )

        self.assertFalse(result.dry_run)
        self.assertEqual(result.safety_evidence_inserted, 1)
        self.assertEqual(result.quote_evidence_inserted, 2)
        self.assertEqual(result.clean_evidence_inserted, 3)
        self.assertEqual(result.audit_only_evidence_inserted, 0)
        self.assertEqual(result.rejected_or_failed, 0)
        self.assertEqual(self.row_count("printer_solana_safety_evidence"), 1)
        self.assertEqual(self.row_count("printer_paper_quote_evidence"), 2)
        self.assertEqual(self.row_count("printer_source_requests"), 3)
        self.assertEqual(self.row_count("printer_source_responses"), 3)
        self.assertTrue(all(item.source_request_id for item in result.item_results))
        self.assertTrue(all(set(item.downstream_unlocks.values()) == {False} for item in result.item_results))

    def test_missing_source_trace_is_rejected_by_existing_guarded_helpers(self):
        safety = normalize_solana_rpc_safety_fixture_payload(
            valid_safety_payload(),
            token_id=1,
            pair_id=1,
            snapshot_id=1,
            source_request_id=1,
            source_response_id=None,
        )
        safety_result = insert_solana_safety_evidence(
            self.connection,
            safety,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=SAFETY_ALLOWED_CALLER,
        )
        self.assertFalse(safety_result.inserted)
        self.assertIn("SOURCE_TRACE_MISSING", safety_result.rejection_reasons)

        quote = normalize_jupiter_quote_fixture_payload(
            valid_quote_payload(),
            quote_direction="ENTRY",
            token_id=1,
            pair_id=1,
            snapshot_id=1,
            source_request_id=1,
            source_response_id=None,
        )
        quote_result = insert_paper_quote_evidence(
            self.connection,
            quote,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=QUOTE_ALLOWED_CALLER,
        )
        self.assertFalse(quote_result.inserted)
        self.assertIn("SOURCE_TRACE_MISSING", quote_result.rejection_reasons)

    def test_target_mismatch_is_rejected_for_safety_and_quote(self):
        result = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload=valid_safety_payload(target_status="TARGET_MISMATCH"),
            entry_quote_payload=valid_quote_payload(target_status="TARGET_MISMATCH"),
        )

        self.assertEqual(result.safety_evidence_inserted, 0)
        self.assertEqual(result.quote_evidence_inserted, 0)
        self.assertEqual(result.rejected_or_failed, 2)
        for item in result.item_results:
            self.assertIn("TARGET_MISMATCH", item.rejection_reasons)

    def test_partial_placeholder_safety_and_quote_cannot_become_clean_evidence(self):
        result = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload={
                "captured_at": "2026-06-23T12:00:00+00:00",
                "mint_account": {"mint_authority": None},
                "source_status": "PARTIAL",
                "data_quality_label": "ACCEPTABLE_PARTIAL_DATA",
            },
            entry_quote_payload={
                "route_plan_present": True,
                "quote_captured_at": "2026-06-23T12:00:00+00:00",
                "source_status": "PARTIAL",
                "data_quality_label": "ACCEPTABLE_PARTIAL_DATA",
            },
        )

        self.assertEqual(result.clean_evidence_inserted, 0)
        self.assertEqual(result.audit_only_evidence_inserted, 2)
        self.assertEqual(result.rejected_or_failed, 0)
        self.assertFalse(any(item.clean_eligible for item in result.item_results))

    def test_failed_stale_and_dirty_evidence_cannot_become_clean(self):
        failed = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload=valid_safety_payload(source_status="FAILED", data_quality_label="MISSING_CRITICAL_DATA"),
            entry_quote_payload=valid_quote_payload(source_status="FAILED", data_quality_label="MISSING_CRITICAL_DATA"),
        )
        self.assertEqual(failed.clean_evidence_inserted, 0)
        self.assertTrue(all(not item.clean_eligible for item in failed.item_results))

        stale = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload=valid_safety_payload(source_status="STALE", data_quality_label="STALE_DATA", freshness_label="SAFETY_EVIDENCE_STALE"),
            entry_quote_payload=valid_quote_payload(source_status="STALE", data_quality_label="STALE_DATA", freshness_label="QUOTE_STALE"),
        )
        self.assertEqual(stale.clean_evidence_inserted, 0)
        self.assertTrue(all(not item.clean_eligible for item in stale.item_results))

        dirty = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload=valid_safety_payload(data_quality_label="DIRTY_DATA"),
        )
        self.assertEqual(dirty.clean_evidence_inserted, 0)
        self.assertEqual(dirty.rejected_or_failed, 1)
        self.assertIn("DATA_QUALITY_NOT_INSERTABLE", dirty.item_results[0].rejection_reasons)

    def test_no_persistent_db_or_downstream_state_is_mutated(self):
        persistent_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        before_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None
        before_downstream = self.downstream_counts()

        result = fill_controlled_governed_evidence(
            self.connection,
            target=self.target,
            safety_payload=valid_safety_payload(),
            entry_quote_payload=valid_quote_payload(),
            exit_quote_payload=valid_quote_payload(),
        )

        after_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None
        self.assertEqual(before_mtime, after_mtime)
        self.assertEqual(before_downstream, self.downstream_counts())
        self.assertEqual(result.clean_evidence_inserted, 3)

    def test_controlled_fill_helper_has_no_live_or_forbidden_capability_terms(self):
        source_text = (
            PROJECT_ROOT / "src" / "printer_v1" / "evidence_fill" / "controlled.py"
        ).read_text(encoding="utf-8")
        forbidden_terms = (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "os.environ",
            "RPC_URL",
            "API_KEY",
            "private_key",
            "signed_tx",
            "execute_trade",
            "transaction_signature",
            "tx_signature",
            "confidence_score",
            "buy_score",
            "rank_score",
            "score =",
            "while True",
        )
        for term in forbidden_terms:
            with self.subTest(term=term):
                self.assertNotIn(term, source_text)


if __name__ == "__main__":
    unittest.main()
