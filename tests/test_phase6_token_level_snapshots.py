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
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.scheduler.contracts import JobStatus
from printer_v1.snapshots import coverage, frequency, quality, recorder
from printer_v1.snapshots.contracts import (
    CoverageLabel,
    QuoteRouteStatus,
    SnapshotGapLabel,
    SnapshotMode,
    SnapshotQualityLabel,
)


REQUIRED_SNAPSHOT_MODES = {
    "NORMAL_MODE",
    "MICRO_EVENT_MODE",
    "DUMP_MODE",
    "CONSOLIDATION_MODE",
    "REVIVAL_MODE",
    "WINDOW_CLOSE_MODE",
    "PAPER_EXIT_PROTECTION_MODE",
}

REQUIRED_QUALITY_LABELS = {
    "CLEAN_SNAPSHOT",
    "PARTIAL_SNAPSHOT",
    "DIRTY_SNAPSHOT",
    "STALE_SNAPSHOT",
    "MISSING_CRITICAL_FIELDS",
    "CONFLICTING_SNAPSHOT",
    "DO_NOT_USE_FOR_MEMORY",
}

REQUIRED_GAP_LABELS = {
    "NO_GAP",
    "MINOR_GAP",
    "MAJOR_GAP",
    "WINDOW_BROKEN",
    "MISSED_WINDOW_CLOSE",
}

REQUIRED_COVERAGE_LABELS = {
    "FULL_COVERAGE",
    "ACCEPTABLE_COVERAGE",
    "PARTIAL_COVERAGE",
    "BROKEN_COVERAGE",
    "AUDIT_ONLY_COVERAGE",
}

REQUIRED_QUOTE_ROUTE_LABELS = {
    "QUOTE_NOT_REQUIRED",
    "QUOTE_AVAILABLE",
    "QUOTE_STALE",
    "QUOTE_FAILED",
    "ROUTE_NOT_AVAILABLE",
    "PAPER_ONLY_QUOTE",
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


class Phase6TokenLevelSnapshotsTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "printer.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 19, 12, 0, tzinfo=timezone.utc)
        self.token_index = 0

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
        self.token_index += 1
        token_mint = f"snapshot-mint-{self.token_index}"
        pair_address = f"snapshot-pair-{self.token_index}"
        with self.connect() as connection:
            token_id = connection.execute(
                """
                INSERT INTO printer_tokens (token_mint, chain, symbol, name)
                VALUES (?, 'solana', 'SNAP', 'Snapshot Coin')
                """,
                (token_mint,),
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
                VALUES (?, ?, 'raydium', 'local', ?, 'So111')
                """,
                (token_id, pair_address, token_mint),
            ).lastrowid
        return int(token_id), int(pair_id)

    def base_payload(self, *, captured_at=None):
        token_id, pair_id = self.insert_token_pair()
        return {
            "token_id": token_id,
            "pair_id": pair_id,
            "captured_at": (captured_at or self.now).isoformat(),
            "tracking_lane": TokenLifecycleState.TRACK_FAST.value,
            "snapshot_mode": SnapshotMode.NORMAL_MODE.value,
            "price_usd": 0.01,
            "price_native": 0.00001,
            "liquidity_usd": 12000,
            "volume_5m": 250,
            "volume_15m": 800,
            "volume_1h": 2200,
            "txns_5m": 8,
            "txns_15m": 18,
            "source_status": SourceStatus.COMPLETE.value,
            "data_quality_label": DataQualityLabel.CLEAN_DATA.value,
        }

    def count_rows(self, table):
        with self.connect() as connection:
            return connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def test_discovery_package_has_dunder_init_not_accidental_init(self):
        self.assertTrue((SRC_PATH / "printer_v1" / "discovery" / "__init__.py").exists())
        self.assertFalse((SRC_PATH / "printer_v1" / "discovery" / "init.py").exists())

    def test_snapshot_files_import_successfully(self):
        self.assertTrue(inspect.ismodule(quality))
        self.assertTrue(inspect.ismodule(frequency))
        self.assertTrue(inspect.ismodule(recorder))
        self.assertTrue(inspect.ismodule(coverage))

    def test_all_required_snapshot_contract_labels_exist(self):
        self.assertEqual({mode.value for mode in SnapshotMode}, REQUIRED_SNAPSHOT_MODES)
        self.assertEqual(
            {label.value for label in SnapshotQualityLabel},
            REQUIRED_QUALITY_LABELS,
        )
        self.assertEqual({label.value for label in SnapshotGapLabel}, REQUIRED_GAP_LABELS)
        self.assertEqual({label.value for label in CoverageLabel}, REQUIRED_COVERAGE_LABELS)
        self.assertEqual(
            {label.value for label in QuoteRouteStatus},
            REQUIRED_QUOTE_ROUTE_LABELS,
        )

    def test_missing_critical_fields_become_missing_critical_fields(self):
        payload = self.base_payload()
        del payload["price_usd"]
        self.assertEqual(
            quality.classify_snapshot_quality(payload, self.now),
            SnapshotQualityLabel.MISSING_CRITICAL_FIELDS,
        )

    def test_clean_snapshot_payload_becomes_clean_snapshot(self):
        self.assertEqual(
            quality.classify_snapshot_quality(self.base_payload(), self.now),
            SnapshotQualityLabel.CLEAN_SNAPSHOT,
        )

    def test_stale_payload_becomes_stale_snapshot(self):
        payload = self.base_payload(captured_at=self.now - timedelta(hours=2))
        self.assertEqual(
            quality.classify_snapshot_quality(payload, self.now),
            SnapshotQualityLabel.STALE_SNAPSHOT,
        )

    def test_dirty_data_label_becomes_dirty_snapshot(self):
        payload = self.base_payload()
        payload["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        self.assertEqual(
            quality.classify_snapshot_quality(payload, self.now),
            SnapshotQualityLabel.DIRTY_SNAPSHOT,
        )

    def test_conflicting_source_or_data_becomes_conflicting_snapshot(self):
        payload = self.base_payload()
        payload["source_status"] = SourceStatus.CONFLICTING.value
        self.assertEqual(
            quality.classify_snapshot_quality(payload, self.now),
            SnapshotQualityLabel.CONFLICTING_SNAPSHOT,
        )

    def test_dirty_stale_conflicting_snapshots_cannot_support_clean_memory(self):
        dirty = self.base_payload()
        dirty["data_quality_label"] = DataQualityLabel.DIRTY_DATA.value
        stale = self.base_payload(captured_at=self.now - timedelta(hours=2))
        conflicting = self.base_payload()
        conflicting["source_status"] = SourceStatus.CONFLICTING.value
        for payload in (dirty, stale, conflicting):
            self.assertFalse(quality.snapshot_can_support_clean_memory(payload, self.now))

    def test_normalizer_preserves_core_fields(self):
        payload = self.base_payload()
        normalized = quality.normalize_snapshot_payload(payload)
        for field in ("token_id", "pair_id", "captured_at", "tracking_lane", "snapshot_mode"):
            self.assertEqual(normalized[field], payload[field])

    def test_snapshot_intervals_protect_high_priority_lanes(self):
        paper = frequency.get_base_snapshot_interval_seconds(
            TokenLifecycleState.PAPER_MONITORING,
            SnapshotMode.NORMAL_MODE,
        )
        fast = frequency.get_base_snapshot_interval_seconds(
            TokenLifecycleState.TRACK_FAST,
            SnapshotMode.NORMAL_MODE,
            token_age_seconds=60,
        )
        normal = frequency.get_base_snapshot_interval_seconds(
            TokenLifecycleState.TRACK_NORMAL,
            SnapshotMode.NORMAL_MODE,
            token_age_seconds=60,
        )
        watch = frequency.get_base_snapshot_interval_seconds(
            TokenLifecycleState.WATCH_ONLY,
            SnapshotMode.NORMAL_MODE,
        )
        self.assertLess(paper, fast)
        self.assertLess(fast, normal)
        self.assertLess(normal, watch)

    def test_window_close_and_exit_protection_modes_are_fast(self):
        near_close = self.now + timedelta(seconds=30)
        self.assertTrue(frequency.should_force_window_close_snapshot(self.now, near_close))
        self.assertEqual(
            frequency.get_base_snapshot_interval_seconds(
                TokenLifecycleState.TRACK_FAST,
                SnapshotMode.PAPER_EXIT_PROTECTION_MODE,
            ),
            60,
        )

    def test_record_token_snapshot_inserts_and_dedupes_snapshot_row(self):
        payload = self.base_payload()
        created, snapshot_id = recorder.record_token_snapshot(self.db_path, payload, self.now)
        self.assertTrue(created)
        duplicate_created, duplicate_id = recorder.record_token_snapshot(
            self.db_path,
            payload,
            self.now,
        )
        self.assertFalse(duplicate_created)
        self.assertEqual(snapshot_id, duplicate_id)
        self.assertEqual(self.count_rows("printer_token_snapshots"), 1)

    def test_latest_and_window_snapshot_lookup(self):
        payload = self.base_payload()
        later = dict(payload)
        later["captured_at"] = (self.now + timedelta(minutes=2)).isoformat()
        recorder.record_token_snapshot(self.db_path, payload, self.now)
        recorder.record_token_snapshot(self.db_path, later, self.now + timedelta(minutes=2))
        latest = recorder.get_latest_snapshot(
            self.db_path,
            token_id=payload["token_id"],
            pair_id=payload["pair_id"],
        )
        self.assertEqual(latest["captured_at"], later["captured_at"])
        rows = recorder.get_snapshots_for_window(
            self.db_path,
            payload["token_id"],
            payload["pair_id"],
            self.now,
            self.now + timedelta(minutes=3),
        )
        self.assertEqual([row["captured_at"] for row in rows], [payload["captured_at"], later["captured_at"]])

    def test_snapshot_gap_detection_finds_missed_intervals(self):
        snapshots = [
            {"captured_at": self.now.isoformat()},
            {"captured_at": (self.now + timedelta(minutes=8)).isoformat()},
        ]
        gaps = coverage.detect_snapshot_gaps(
            snapshots,
            expected_interval_seconds=120,
            opened_at=self.now,
            closed_at=self.now + timedelta(minutes=10),
        )
        self.assertTrue(any(gap.snapshot_gap_label != SnapshotGapLabel.NO_GAP for gap in gaps))

    def test_coverage_classification_marks_full_and_broken_windows(self):
        full = coverage.calculate_coverage(
            self.now,
            self.now + timedelta(minutes=4),
            [
                {"captured_at": self.now.isoformat()},
                {"captured_at": (self.now + timedelta(minutes=2)).isoformat()},
                {"captured_at": (self.now + timedelta(minutes=4)).isoformat()},
            ],
            expected_interval_seconds=120,
        )
        broken = coverage.calculate_coverage(
            self.now,
            self.now + timedelta(minutes=10),
            [{"captured_at": self.now.isoformat()}],
            expected_interval_seconds=120,
        )
        self.assertEqual(full.coverage_label, CoverageLabel.FULL_COVERAGE)
        self.assertEqual(broken.coverage_label, CoverageLabel.BROKEN_COVERAGE)

    def test_gap_audit_rows_are_written(self):
        token_id, pair_id = self.insert_token_pair()
        audit_id = recorder.record_snapshot_gap_audit(
            self.db_path,
            token_id=token_id,
            pair_id=pair_id,
            tracking_lane=TokenLifecycleState.TRACK_FAST,
            snapshot_mode=SnapshotMode.NORMAL_MODE,
            expected_captured_at=self.now,
            actual_captured_at=self.now + timedelta(minutes=8),
            gap_seconds=480,
            snapshot_gap_label=SnapshotGapLabel.MAJOR_GAP,
            coverage_label=CoverageLabel.BROKEN_COVERAGE,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
        )
        self.assertGreater(audit_id, 0)
        self.assertEqual(self.count_rows("printer_snapshot_gap_audits"), 1)

    def test_snapshot_window_coverage_rows_are_written(self):
        token_id, pair_id = self.insert_token_pair()
        window_coverage = coverage.WindowCoverage(
            expected_snapshot_count=5,
            actual_snapshot_count=1,
            missing_snapshot_count=4,
            max_gap_seconds=600,
            coverage_label=CoverageLabel.BROKEN_COVERAGE,
        )
        coverage_id = coverage.write_snapshot_window_coverage(
            self.db_path,
            token_id=token_id,
            pair_id=pair_id,
            window_kind="15m",
            tracking_lane=TokenLifecycleState.TRACK_FAST,
            opened_at=self.now,
            closed_at=self.now + timedelta(minutes=15),
            coverage=window_coverage,
        )
        self.assertGreater(coverage_id, 0)
        with self.connect() as connection:
            row = connection.execute(
                "SELECT memory_status, do_not_train FROM printer_snapshot_window_coverage"
            ).fetchone()
        self.assertEqual(row["memory_status"], "DO_NOT_TRAIN")
        self.assertEqual(row["do_not_train"], 1)

    def test_scheduler_integration_enqueues_rows_only(self):
        token_id, pair_id = self.insert_token_pair()
        result, job_id = recorder.enqueue_next_snapshot_job(
            self.db_path,
            token_id,
            pair_id,
            TokenLifecycleState.TRACK_FAST,
            SnapshotMode.NORMAL_MODE,
            self.now + timedelta(minutes=2),
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

    def test_no_paper_decision_or_position_rows_are_created(self):
        recorder.record_token_snapshot(self.db_path, self.base_payload(), self.now)
        self.assertEqual(self.count_rows("printer_paper_decisions"), 0)
        self.assertEqual(self.count_rows("printer_paper_positions"), 0)

    def test_no_network_source_adapter_loop_or_forbidden_concepts_exist(self):
        source_text = "\n".join(
            inspect.getsource(module)
            for module in (quality, frequency, recorder, coverage)
        )
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
        for module in (quality, frequency, recorder, coverage):
            names.extend(name.lower() for name, _ in inspect.getmembers(module))
        joined_names = " ".join(names)
        self.assertFalse(any(fragment in joined_names for fragment in FORBIDDEN_FRAGMENTS))


if __name__ == "__main__":
    unittest.main()
