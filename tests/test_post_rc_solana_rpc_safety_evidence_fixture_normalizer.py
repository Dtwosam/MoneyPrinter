import inspect
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
from printer_v1.safety.evidence import ALLOWED_CALLER, insert_solana_safety_evidence
from printer_v1.safety.solana_rpc_fixture import (
    insert_solana_rpc_safety_evidence_from_source_response,
    normalize_solana_rpc_safety_fixture_payload,
)
from printer_v1.sources import (
    build_fixture_source_adapter,
    build_governed_source_request,
    execute_source_request_with_governor,
)


def valid_rpc_payload(**overrides):
    payload = {
        "captured_at": "2026-06-23T12:00:00+00:00",
        "mint_account": {
            "mint_authority": None,
            "freeze_authority": None,
            "token_program": "spl_token",
        },
        "metadata": {
            "mutable": False,
        },
        "supply": {
            "supply": "1000000000",
        },
        "holders": {
            "top_holder_percent": 4.5,
            "top_10_holder_percent": 32.0,
        },
        "liquidity": {
            "lock_or_burn_status": "confirmed",
        },
        "risk_flags": [],
        "target_status": "TARGET_MATCH",
        "freshness_label": "SAFETY_EVIDENCE_FRESH",
    }
    payload.update(overrides)
    return payload


class PostRcSolanaRpcSafetyEvidenceFixtureNormalizerTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.connection = sqlite3.connect(self.db_path)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.seed_base_rows()

    def tearDown(self):
        self.connection.rollback()
        self.connection.close()
        self.tempdir.cleanup()

    def seed_base_rows(self):
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

    def table_count(self, table_name):
        return self.connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]

    def source_fixture(self, payload):
        request = build_governed_source_request(
            "solana_rpc",
            "mint_account_reference",
            request_key="fixture-mint",
            payload={"token_mint": "fixture-mint"},
        )
        adapter = build_fixture_source_adapter(
            "solana_rpc",
            fixture_payload=payload,
        )
        return execute_source_request_with_governor(self.connection, request, adapter)

    def insert_from_payload(self, payload):
        result = self.source_fixture(payload)
        self.assertIsNotNone(result.response_record)
        return insert_solana_rpc_safety_evidence_from_source_response(
            self.connection,
            source_response_id=result.response_record.id,
            token_id=1,
            pair_id=1,
            snapshot_id=1,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
        )

    def source_trace_ids(self):
        result = self.source_fixture(valid_rpc_payload())
        self.assertIsNotNone(result.response_record)
        return result.request_record.id, result.response_record.id

    def test_valid_fixture_creates_one_guarded_safety_evidence_row(self):
        result = self.insert_from_payload(valid_rpc_payload())

        self.assertTrue(result.inserted)
        self.assertTrue(result.clean_eligible)
        self.assertEqual(result.source_trace_status, "SOURCE_TRACE_PRESENT")
        self.assertEqual(set(result.downstream_unlocks.values()), {False})
        self.assertEqual(self.table_count("printer_solana_safety_evidence"), 1)

        row = self.connection.execute(
            "SELECT * FROM printer_solana_safety_evidence WHERE id = ?",
            (result.evidence_id,),
        ).fetchone()
        self.assertEqual(row["source_name"], "solana_rpc")
        self.assertEqual(row["source_request_id"], 1)
        self.assertEqual(row["source_response_id"], 1)
        self.assertIsNone(row["source_failure_id"])
        self.assertEqual(row["mint_authority_status"], "MINT_AUTHORITY_RENOUNCED")
        self.assertEqual(row["freeze_authority_status"], "FREEZE_AUTHORITY_DISABLED")
        self.assertEqual(row["metadata_mutability_status"], "METADATA_IMMUTABLE")
        self.assertEqual(row["token_program_label"], "SPL_TOKEN_OR_TOKEN_2022_VERIFIED")
        self.assertEqual(row["safety_context_label"], "SAFETY_CLEAN")
        self.assertEqual(row["paper_only_context"], 1)

    def test_missing_required_safety_fields_are_unknown_and_not_clean(self):
        cases = {
            "mint_authority": {"mint_account": {"freeze_authority": None, "token_program": "spl_token"}},
            "freeze_authority": {"mint_account": {"mint_authority": None, "token_program": "spl_token"}},
            "metadata_mutability": {"metadata": {}},
            "token_program": {"mint_account": {"mint_authority": None, "freeze_authority": None}},
            "holders": {"holders": {}},
            "liquidity_lock": {"liquidity": {}},
            "risk_flags": {"risk_flags": None},
        }

        for name, overrides in cases.items():
            with self.subTest(name=name):
                source_request_id, source_response_id = self.source_trace_ids()
                evidence = normalize_solana_rpc_safety_fixture_payload(
                    valid_rpc_payload(**overrides),
                    token_id=1,
                    pair_id=1,
                    snapshot_id=1,
                    source_request_id=source_request_id,
                    source_response_id=source_response_id,
                )
                self.assertEqual(evidence["safety_context_label"], "SAFETY_UNKNOWN")
                self.assertFalse(
                    insert_solana_safety_evidence(
                        self.connection,
                        evidence,
                        scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                        operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                        caller=ALLOWED_CALLER,
                    ).clean_eligible
                )

    def test_partial_placeholder_payload_cannot_produce_clean_safety_evidence(self):
        result = self.insert_from_payload(
            {
                "captured_at": "2026-06-23T12:00:00+00:00",
                "mint_account": {"mint_authority": None},
                "source_status": "PARTIAL",
                "data_quality_label": "ACCEPTABLE_PARTIAL_DATA",
            }
        )

        self.assertTrue(result.inserted)
        self.assertFalse(result.clean_eligible)
        row = self.connection.execute("SELECT * FROM printer_solana_safety_evidence").fetchone()
        self.assertEqual(row["safety_context_label"], "SAFETY_UNKNOWN")

    def test_failed_stale_dirty_and_target_mismatch_are_not_clean(self):
        cases = [
            valid_rpc_payload(source_status="FAILED", data_quality_label="MISSING_CRITICAL_DATA"),
            valid_rpc_payload(source_status="STALE", data_quality_label="STALE_DATA", freshness_label="SAFETY_EVIDENCE_STALE"),
            valid_rpc_payload(data_quality_label="DIRTY_DATA"),
        ]
        for payload in cases:
            with self.subTest(status=payload.get("source_status"), quality=payload.get("data_quality_label")):
                source_request_id, source_response_id = self.source_trace_ids()
                evidence = normalize_solana_rpc_safety_fixture_payload(
                    payload,
                    token_id=1,
                    pair_id=1,
                    snapshot_id=1,
                    source_request_id=source_request_id,
                    source_response_id=source_response_id,
                )
                result = insert_solana_safety_evidence(
                    self.connection,
                    evidence,
                    scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
                    operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
                    caller=ALLOWED_CALLER,
                )
                self.assertFalse(result.clean_eligible)

        mismatch = self.insert_from_payload(valid_rpc_payload(target_status="TARGET_MISMATCH"))
        self.assertFalse(mismatch.inserted)
        self.assertIn("TARGET_MISMATCH", mismatch.rejection_reasons)

    def test_direct_engine_callers_and_missing_source_trace_are_blocked(self):
        source_request_id, source_response_id = self.source_trace_ids()
        evidence = normalize_solana_rpc_safety_fixture_payload(
            valid_rpc_payload(),
            token_id=1,
            pair_id=1,
            snapshot_id=1,
            source_request_id=source_request_id,
            source_response_id=source_response_id,
        )
        direct = insert_solana_safety_evidence(
            self.connection,
            evidence,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller="memory_engine",
        )
        self.assertFalse(direct.inserted)
        self.assertIn("DIRECT_CALLER_FORBIDDEN", direct.rejection_reasons)

        evidence["source_response_id"] = None
        missing_trace = insert_solana_safety_evidence(
            self.connection,
            evidence,
            scheduler_boundary_label="SCHEDULER_BOUNDARY_PRESENT",
            operator_approval_label="OPERATOR_APPROVED_MANUAL_PROOF",
            caller=ALLOWED_CALLER,
        )
        self.assertFalse(missing_trace.inserted)
        self.assertIn("SOURCE_TRACE_MISSING", missing_trace.rejection_reasons)

    def test_no_live_network_rpc_api_path_or_forbidden_fields_exist(self):
        import printer_v1.safety.solana_rpc_fixture as module

        source_text = pathlib.Path(module.__file__).read_text(encoding="utf-8")
        for fragment in (
            "urlopen",
            "requests.",
            "httpx",
            "aiohttp",
            "websocket",
            "socket.",
            "os.environ",
            "RPC_URL",
            "endpoint",
            "wallet",
            "private_key",
            "signature",
            "signer",
            "live_execution",
            "score",
            "rank",
            "confidence",
            "weighted",
        ):
            self.assertNotIn(fragment, source_text)

        public_functions = {
            name
            for name, member in inspect.getmembers(module, predicate=inspect.isfunction)
            if not name.startswith("_") and member.__module__ == module.__name__
        }
        self.assertEqual(
            public_functions,
            {
                "insert_solana_rpc_safety_evidence_from_source_response",
                "normalize_solana_rpc_safety_fixture_payload",
            },
        )

    def test_insert_creates_no_downstream_rows_and_persistent_db_is_untouched(self):
        persistent_db = PROJECT_ROOT / "data" / "printer_v1.sqlite3"
        before_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None

        result = self.insert_from_payload(valid_rpc_payload())

        after_mtime = persistent_db.stat().st_mtime_ns if persistent_db.exists() else None
        self.assertTrue(result.inserted)
        self.assertEqual(before_mtime, after_mtime)
        for table_name in (
            "printer_memory_windows",
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
        ):
            self.assertEqual(self.table_count(table_name), 0, table_name)


if __name__ == "__main__":
    unittest.main()
