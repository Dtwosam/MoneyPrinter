import inspect
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.safety import classifier, lookup, parser, recorder
from printer_v1.safety.classifier import (
    classify_authority_safety,
    classify_distribution_safety,
    classify_liquidity_safety,
    classify_rug_risk,
    classify_safety_status,
    safety_context_can_support_clean_memory,
)
from printer_v1.safety.contracts import (
    AuthorityLabel,
    DistributionLabel,
    LiquiditySafetyLabel,
    RugRiskLabel,
    SafetyGateLabel,
    SafetyPayloadQualityLabel,
    SafetyStatusLabel,
)
from printer_v1.safety.parser import normalize_safety_payload, validate_safety_payload
from printer_v1.safety.recorder import (
    enqueue_safety_rug_refresh_job,
    get_latest_safety_rug_snapshot,
    record_safety_rug_snapshot,
)
from printer_v1.scheduler.contracts import JobStatus


REQUIRED_SAFETY_LABELS = {
    "SAFETY_CLEAN",
    "SAFETY_CAUTION",
    "SAFETY_SUSPICIOUS",
    "SAFETY_UNSAFE",
    "SAFETY_UNKNOWN",
    "SAFETY_DO_NOT_USE_FOR_MEMORY",
}
REQUIRED_RUG_LABELS = {
    "RUG_RISK_LOW",
    "RUG_RISK_MEDIUM",
    "RUG_RISK_HIGH",
    "RUG_RISK_CRITICAL",
    "RUG_RISK_UNKNOWN",
}
REQUIRED_LIQUIDITY_LABELS = {
    "LIQUIDITY_SAFE",
    "LIQUIDITY_THIN",
    "LIQUIDITY_UNSTABLE",
    "LIQUIDITY_LOCK_UNKNOWN",
    "LIQUIDITY_DANGEROUS",
    "LIQUIDITY_SAFETY_UNKNOWN",
}
REQUIRED_AUTHORITY_LABELS = {
    "AUTHORITY_RENOUNCED_OR_SAFE",
    "AUTHORITY_PRESENT",
    "AUTHORITY_SUSPICIOUS",
    "AUTHORITY_DANGEROUS",
    "AUTHORITY_UNKNOWN",
}
REQUIRED_DISTRIBUTION_LABELS = {
    "DISTRIBUTION_HEALTHY",
    "DISTRIBUTION_CONCENTRATED",
    "DISTRIBUTION_EXTREME_CONCENTRATION",
    "DISTRIBUTION_UNKNOWN",
}
REQUIRED_QUALITY_LABELS = {
    "SAFETY_CONTEXT_CLEAN",
    "SAFETY_CONTEXT_PARTIAL",
    "SAFETY_CONTEXT_STALE",
    "SAFETY_CONTEXT_CONFLICTING",
    "SAFETY_CONTEXT_UNKNOWN",
    "SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY",
}
REQUIRED_GATE_LABELS = {
    "ALLOW_SAFETY_CONTEXT",
    "CAUTION_SAFETY_CONTEXT",
    "BLOCK_UNSAFE_CONTEXT",
    "MANUAL_REVIEW_REQUIRED",
    "DO_NOT_TRAIN_SAFETY_CONTEXT",
}
FORBIDDEN_COLUMNS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet_address",
    "private_key",
    "signed_tx",
    "live_trade",
}
FORBIDDEN_FRAGMENTS = {
    "score",
    "confidence",
    "rank",
    "rating",
    "weight",
    "wallet",
    "private_key",
    "signed_tx",
    "live_trade",
}


class Phase9SafetyRugFilterEngineTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
        self.token_id, self.pair_id = self.insert_token_pair()

    def tearDown(self):
        self.tempdir.cleanup()

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def insert_token_pair(self):
        with self.connect() as connection:
            token_id = connection.execute(
                """
                INSERT INTO printer_tokens (token_mint, chain, symbol, name)
                VALUES ('safety-mint', 'solana', 'SAFE', 'Safety Coin')
                """
            ).lastrowid
            pair_id = connection.execute(
                """
                INSERT INTO printer_pairs (
                    token_id,
                    pair_address,
                    dex,
                    pool_source,
                    base_token_mint,
                    quote_token_mint
                )
                VALUES (?, 'safety-pair', 'raydium', 'local', 'safety-mint', 'So111')
                """,
                (token_id,),
            ).lastrowid
        return int(token_id), int(pair_id)

    def payload(self, *, captured_at=None, **overrides):
        base = {
            "token": {"token_id": self.token_id, "mint": "safety-mint"},
            "pair": {"pair_id": self.pair_id, "pair_address": "safety-pair"},
            "captured_at": (captured_at or self.now).isoformat(),
            "liquidity": {
                "usd": 80_000,
                "locked": True,
                "lock_source": "local_fixture",
                "lock_until": (self.now + timedelta(days=30)).isoformat(),
            },
            "authority": {
                "mint_authority_present": False,
                "freeze_authority_present": False,
                "update_authority_present": False,
                "transfer_fee_present": False,
                "blacklist_function_present": False,
            },
            "distribution": {
                "holder_count": 1200,
                "top_holder_percent": 4.0,
                "top_5_holder_percent": 18.0,
                "top_10_holder_percent": 32.0,
                "creator_percent": 2.0,
            },
            "restrictions": {
                "honeypot_like_behavior": False,
                "sell_restriction_detected": False,
                "buy_restriction_detected": False,
            },
            "metadata": {
                "mutable_metadata": False,
                "suspicious_metadata": False,
            },
            "creator": {"suspicious_creator_activity": False},
            "source_name": "local_fixture",
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }
        for key, value in overrides.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                base[key].update(value)
            else:
                base[key] = value
        return base

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def table_names(self):
        with self.connect() as connection:
            return {
                row[0]
                for row in connection.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                ).fetchall()
            }

    def column_names(self, table_name):
        with self.connect() as connection:
            return {
                row[1]
                for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
            }

    def test_chain_heat_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "chain_heat" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "chain_heat" / "init.py").exists())

    def test_safety_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(parser))
        self.assertTrue(inspect.ismodule(classifier))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(lookup))

    def test_required_contract_labels_exist(self):
        self.assertEqual({label.value for label in SafetyStatusLabel}, REQUIRED_SAFETY_LABELS)
        self.assertEqual({label.value for label in RugRiskLabel}, REQUIRED_RUG_LABELS)
        self.assertEqual({label.value for label in LiquiditySafetyLabel}, REQUIRED_LIQUIDITY_LABELS)
        self.assertEqual({label.value for label in AuthorityLabel}, REQUIRED_AUTHORITY_LABELS)
        self.assertEqual({label.value for label in DistributionLabel}, REQUIRED_DISTRIBUTION_LABELS)
        self.assertEqual({label.value for label in SafetyPayloadQualityLabel}, REQUIRED_QUALITY_LABELS)
        self.assertEqual({label.value for label in SafetyGateLabel}, REQUIRED_GATE_LABELS)

    def test_migration_creates_safety_table_without_forbidden_columns(self):
        self.assertIn("printer_safety_rug_snapshots", self.table_names())
        forbidden_found = self.column_names("printer_safety_rug_snapshots") & FORBIDDEN_COLUMNS
        self.assertEqual(forbidden_found, set())

    def test_parser_normalizes_fake_goplus_style_payload(self):
        normalized = normalize_safety_payload(self.payload(), self.now)
        self.assertEqual(normalized["token_mint"], "safety-mint")
        self.assertEqual(normalized["pair_address"], "safety-pair")
        self.assertEqual(normalized["liquidity_usd"], 80000.0)
        self.assertEqual(normalized["mint_authority_present"], 0)

    def test_parser_normalizes_fake_local_authority_distribution_payload(self):
        normalized = normalize_safety_payload(
            self.payload(
                authority={"freeze_authority_present": True},
                distribution={"top_10_holder_percent": 70.0},
            ),
            self.now,
        )
        self.assertEqual(normalized["freeze_authority_present"], 1)
        self.assertEqual(normalized["top_10_holder_percent"], 70.0)

    def test_parser_labels_missing_critical_context_as_not_clean(self):
        self.assertIn(
            validate_safety_payload({"captured_at": self.now.isoformat()}, self.now),
            {
                SafetyPayloadQualityLabel.SAFETY_CONTEXT_PARTIAL,
                SafetyPayloadQualityLabel.SAFETY_CONTEXT_UNKNOWN,
                SafetyPayloadQualityLabel.SAFETY_CONTEXT_DO_NOT_USE_FOR_MEMORY,
            },
        )

    def test_stale_safety_payload_is_labeled_stale(self):
        self.assertEqual(
            validate_safety_payload(
                self.payload(captured_at=self.now - timedelta(hours=3)),
                self.now,
            ),
            SafetyPayloadQualityLabel.SAFETY_CONTEXT_STALE,
        )

    def test_classifier_identifies_clean_low_risk_context(self):
        normalized = normalize_safety_payload(self.payload(), self.now)
        self.assertEqual(classify_safety_status(normalized), SafetyStatusLabel.SAFETY_CLEAN)
        self.assertEqual(classify_rug_risk(normalized), RugRiskLabel.RUG_RISK_LOW)

    def test_classifier_identifies_suspicious_context(self):
        normalized = normalize_safety_payload(
            self.payload(metadata={"mutable_metadata": True}),
            self.now,
        )
        self.assertEqual(classify_safety_status(normalized), SafetyStatusLabel.SAFETY_CAUTION)

    def test_classifier_identifies_unsafe_critical_rug_context(self):
        normalized = normalize_safety_payload(
            self.payload(restrictions={"sell_restriction_detected": True}),
            self.now,
        )
        self.assertEqual(classify_safety_status(normalized), SafetyStatusLabel.SAFETY_UNSAFE)
        self.assertEqual(classify_rug_risk(normalized), RugRiskLabel.RUG_RISK_CRITICAL)

    def test_classifier_identifies_dangerous_liquidity_authority_distribution(self):
        dangerous_liquidity = normalize_safety_payload(
            self.payload(liquidity={"usd": 1000, "locked": False}),
            self.now,
        )
        dangerous_authority = normalize_safety_payload(
            self.payload(authority={"blacklist_function_present": True}),
            self.now,
        )
        concentrated = normalize_safety_payload(
            self.payload(distribution={"top_holder_percent": 35.0}),
            self.now,
        )
        self.assertEqual(
            classify_liquidity_safety(dangerous_liquidity),
            LiquiditySafetyLabel.LIQUIDITY_DANGEROUS,
        )
        self.assertEqual(
            classify_authority_safety(dangerous_authority),
            AuthorityLabel.AUTHORITY_DANGEROUS,
        )
        self.assertEqual(
            classify_distribution_safety(concentrated),
            DistributionLabel.DISTRIBUTION_EXTREME_CONCENTRATION,
        )

    def test_classifier_returns_unknown_for_insufficient_context(self):
        self.assertEqual(classify_safety_status({}), SafetyStatusLabel.SAFETY_UNKNOWN)

    def test_dirty_stale_conflicting_context_cannot_support_clean_memory(self):
        dirty = normalize_safety_payload(self.payload(), self.now)
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = normalize_safety_payload(self.payload(captured_at=self.now - timedelta(hours=3)), self.now)
        conflicting = normalize_safety_payload(self.payload(), self.now)
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        for payload in (dirty, stale, conflicting):
            self.assertFalse(safety_context_can_support_clean_memory(payload, self.now))

    def test_unsafe_context_blocks_clean_memory_without_paper_decisions(self):
        record_safety_rug_snapshot(
            self.db_path,
            self.payload(restrictions={"honeypot_like_behavior": True}),
            self.now,
        )
        row = lookup.find_latest_safety_rug_snapshot(
            self.db_path,
            token_id=self.token_id,
            pair_id=self.pair_id,
        )
        self.assertTrue(lookup.safety_snapshot_blocks_clean_memory(row))
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)

    def test_record_safety_rug_snapshot_inserts_and_dedupes_row(self):
        created, row_id = record_safety_rug_snapshot(self.db_path, self.payload(), self.now)
        duplicate_created, duplicate_id = record_safety_rug_snapshot(
            self.db_path,
            self.payload(),
            self.now,
        )
        self.assertTrue(created)
        self.assertFalse(duplicate_created)
        self.assertEqual(row_id, duplicate_id)
        self.assertEqual(self.count_rows("printer_safety_rug_snapshots"), 1)

    def test_latest_and_nearest_valid_safety_lookup(self):
        before = self.now - timedelta(minutes=20)
        after = self.now + timedelta(minutes=10)
        record_safety_rug_snapshot(self.db_path, self.payload(captured_at=before), self.now)
        record_safety_rug_snapshot(self.db_path, self.payload(captured_at=after), self.now)
        latest = get_latest_safety_rug_snapshot(
            self.db_path,
            token_id=self.token_id,
            pair_id=self.pair_id,
        )
        nearest = lookup.find_nearest_safety_rug_snapshot(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now,
            max_age_seconds=3600,
        )
        self.assertEqual(latest["captured_at"], after.isoformat())
        self.assertEqual(nearest["captured_at"], after.isoformat())

    def test_nearest_lookup_rejects_stale_dirty_conflicting_snapshots(self):
        dirty = self.payload()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        record_safety_rug_snapshot(self.db_path, dirty, self.now)
        self.assertIsNone(
            lookup.find_nearest_safety_rug_snapshot(
                self.db_path,
                self.token_id,
                self.pair_id,
                self.now,
                max_age_seconds=3600,
            )
        )

    def test_scheduler_integration_creates_rows_only(self):
        result, job_id = enqueue_safety_rug_refresh_job(
            self.db_path,
            self.token_id,
            self.pair_id,
            self.now + timedelta(minutes=5),
            reason="phase9_test",
        )
        self.assertEqual(result.value, "ACQUIRED")
        self.assertIsNotNone(job_id)
        with self.connect() as connection:
            row = connection.execute("SELECT status FROM printer_scheduler_jobs").fetchone()
            running = connection.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs WHERE status = ?",
                (JobStatus.RUNNING.value,),
            ).fetchone()[0]
        self.assertEqual(row["status"], JobStatus.PENDING.value)
        self.assertEqual(running, 0)

    def test_no_paper_rows_or_lifecycle_state_changes_are_created(self):
        record_safety_rug_snapshot(self.db_path, self.payload(), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)
        self.assertEqual(self.count_rows("printer_token_lifecycle_events"), 0)

    def test_no_network_source_adapter_loop_or_forbidden_concepts_exist(self):
        source_text = "\n".join(inspect.getsource(module) for module in (parser, classifier, recorder, lookup))
        for fragment in (
            "requests.get",
            "requests.post",
            "httpx",
            "aiohttp",
            "urllib.request",
            "while True",
            "APScheduler",
        ):
            self.assertNotIn(fragment, source_text)
        names = []
        for module in (parser, classifier, recorder, lookup):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()
