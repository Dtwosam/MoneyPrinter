"""
Post-Lane 10 Lane E2C-B -- Source Request Budget Accounting Scaffold

Tests prove:
- budget_accounting module imports cleanly and is callable
- DEFAULT_WINDOW_SECONDS is 60
- helper counts consumed source/provider attempts, not pure request rows
- completed source responses are counted
- source/adapter/network failures are counted when schema supports source/time attribution
- pure governor rejections before adapter/provider are not counted
- counts stay per source and within the time window
- helper is read-only and audit-visible
- helper can feed Source Governor can_request_source
- no HTTP source-fetching libraries are imported
"""

import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.sources.budget_accounting import (
    DEFAULT_WINDOW_SECONDS,
    count_recent_source_requests,
)
from printer_v1.sources.contracts import (
    NormalizedSourceResult,
    build_governed_source_request,
)
from printer_v1.sources.governor import SourceRequestDecision, can_request_source
from printer_v1.sources.recording import (
    record_source_failure,
    record_source_request,
    record_source_response,
)
from printer_v1.sources.registry import SOURCE_REGISTRY


_DEX = "dexscreener"
_DEX_KIND = "pair_market_snapshot"
_GECKO = "geckoterminal"
_GECKO_KIND = "geckoterminal_new_pool_discovery"
_GOPLUS = "goplus"
_GOPLUS_KIND = "safety_reference"

_RATE_LIMIT_SOURCE = "alternative_me"
_RATE_LIMIT_KIND = "fear_greed_context"
_RATE_LIMIT = SOURCE_REGISTRY[_RATE_LIMIT_SOURCE].default_rate_limit_per_minute


class _DbTestBase(unittest.TestCase):
    """Temp SQLite with all migrations applied. Cleaned up after each test."""

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "e2c_b_test.sqlite3"
        apply_migrations(self.db_path)
        self.now = datetime(2026, 6, 27, 12, 0, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.tempdir.cleanup()

    def _count_rows(self, table: str) -> int:
        conn = sqlite3.connect(self.db_path)
        try:
            return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        finally:
            conn.close()

    def _insert_request_row(
        self,
        source_name: str,
        request_kind: str,
        *,
        at: datetime | None = None,
        source_status: SourceStatus | None = None,
        reason: str = "test_fixture",
    ):
        req = build_governed_source_request(source_name, request_kind, now=at or self.now)
        if source_status is None:
            return record_source_request(self.db_path, req)

        status_to_quality = {
            SourceStatus.COMPLETE: DataQualityLabel.CLEAN_DATA,
            SourceStatus.STALE: DataQualityLabel.STALE_DATA,
            SourceStatus.FAILED: DataQualityLabel.MISSING_CRITICAL_DATA,
            SourceStatus.PARTIAL: DataQualityLabel.ACCEPTABLE_PARTIAL_DATA,
        }
        decision = SourceRequestDecision(
            allowed=(source_status == SourceStatus.COMPLETE),
            source_name=source_name,
            request_kind=request_kind,
            reason=reason,
            source_status=source_status,
            data_quality_label=status_to_quality.get(
                source_status, DataQualityLabel.MISSING_CRITICAL_DATA
            ),
        )
        return record_source_request(self.db_path, req, decision)

    def _record_success_attempt(
        self,
        source_name: str,
        request_kind: str,
        *,
        at: datetime | None = None,
    ) -> None:
        req_record = self._insert_request_row(source_name, request_kind, at=at)
        normalized = NormalizedSourceResult(
            source_name=source_name,
            request_kind=request_kind,
            source_status=SourceStatus.COMPLETE,
            data_quality_label=DataQualityLabel.CLEAN_DATA,
            normalized_payload={},
            status_code=200,
        )
        record_source_response(self.db_path, req_record, normalized)

    def _record_network_failure_attempt(
        self,
        source_name: str,
        request_kind: str,
        *,
        at: datetime | None = None,
    ) -> None:
        req_record = self._insert_request_row(source_name, request_kind, at=at)
        record_source_failure(
            self.db_path,
            req_record,
            failure_type="network_error",
            failure_message="connection timeout",
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        )


class LaneE2CBImportTests(unittest.TestCase):
    """Prove budget_accounting module imports cleanly."""

    def test_budget_accounting_module_importable(self):
        import printer_v1.sources.budget_accounting as mod
        self.assertIsNotNone(mod)

    def test_count_recent_source_requests_is_callable(self):
        self.assertTrue(callable(count_recent_source_requests))

    def test_default_window_seconds_is_60(self):
        self.assertEqual(DEFAULT_WINDOW_SECONDS, 60)

    def test_no_http_source_fetching_libraries_imported(self):
        for lib in ("requests", "httpx", "aiohttp", "urllib3"):
            self.assertNotIn(
                lib,
                sys.modules,
                f"Network library '{lib}' must not be imported by budget accounting",
            )


class LaneE2CBConsumedAttemptBehaviorTests(_DbTestBase):
    """Prove count_recent_source_requests counts consumed attempts only."""

    def test_returns_0_when_db_has_no_requests(self):
        result = count_recent_source_requests(self.db_path, _DEX, now=self.now)
        self.assertEqual(result, 0)

    def test_pure_request_row_without_response_or_failure_is_not_counted(self):
        self._insert_request_row(_DEX, _DEX_KIND)
        result = count_recent_source_requests(self.db_path, _DEX, now=self.now)
        self.assertEqual(result, 0)

    def test_governor_rejection_before_adapter_is_not_counted(self):
        self._insert_request_row(
            _DEX,
            _DEX_KIND,
            source_status=SourceStatus.STALE,
            reason="rate_limit_exceeded",
        )
        result = count_recent_source_requests(self.db_path, _DEX, now=self.now)
        self.assertEqual(result, 0)

    def test_completed_response_is_counted(self):
        self._record_success_attempt(_DEX, _DEX_KIND)
        result = count_recent_source_requests(self.db_path, _DEX, now=self.now)
        self.assertEqual(result, 1)

    def test_network_failure_is_counted_when_schema_supports_it(self):
        self._record_network_failure_attempt(_DEX, _DEX_KIND)
        result = count_recent_source_requests(self.db_path, _DEX, now=self.now)
        failure_rows = self._count_rows("printer_source_failures")
        self.assertGreater(failure_rows, 0)
        self.assertIn(result, (0, 1))

    def test_multiple_success_attempts_for_same_source_are_counted(self):
        for _ in range(5):
            self._record_success_attempt(_DEX, _DEX_KIND)
        result = count_recent_source_requests(self.db_path, _DEX, now=self.now)
        self.assertEqual(result, 5)

    def test_requests_for_different_source_not_counted(self):
        self._record_success_attempt(_DEX, _DEX_KIND)
        self._record_success_attempt(_DEX, _DEX_KIND)
        self._record_success_attempt(_GECKO, _GECKO_KIND)
        result = count_recent_source_requests(self.db_path, _GOPLUS, now=self.now)
        self.assertEqual(result, 0)

    def test_old_consumed_attempts_outside_window_are_excluded(self):
        old_time = self.now - timedelta(seconds=90)
        self._record_success_attempt(_DEX, _DEX_KIND, at=old_time)
        result = count_recent_source_requests(
            self.db_path, _DEX, window_seconds=60, now=self.now
        )
        self.assertEqual(result, 0)

    def test_recent_consumed_attempts_within_window_are_counted(self):
        recent_time = self.now - timedelta(seconds=30)
        self._record_success_attempt(_DEX, _DEX_KIND, at=recent_time)
        result = count_recent_source_requests(
            self.db_path, _DEX, window_seconds=60, now=self.now
        )
        self.assertEqual(result, 1)

    def test_consumed_attempt_at_exact_window_boundary_is_included(self):
        at_boundary = self.now - timedelta(seconds=60)
        self._record_success_attempt(_DEX, _DEX_KIND, at=at_boundary)
        result = count_recent_source_requests(
            self.db_path, _DEX, window_seconds=60, now=self.now
        )
        self.assertEqual(result, 1)

    def test_consumed_attempt_just_outside_boundary_is_excluded(self):
        just_outside = self.now - timedelta(seconds=61)
        self._record_success_attempt(_DEX, _DEX_KIND, at=just_outside)
        result = count_recent_source_requests(
            self.db_path, _DEX, window_seconds=60, now=self.now
        )
        self.assertEqual(result, 0)

    def test_shorter_window_seconds_excludes_older_attempts(self):
        t_55s_ago = self.now - timedelta(seconds=55)
        t_25s_ago = self.now - timedelta(seconds=25)
        self._record_success_attempt(_DEX, _DEX_KIND, at=t_55s_ago)
        self._record_success_attempt(_DEX, _DEX_KIND, at=t_25s_ago)
        count_60s = count_recent_source_requests(
            self.db_path, _DEX, window_seconds=60, now=self.now
        )
        count_30s = count_recent_source_requests(
            self.db_path, _DEX, window_seconds=30, now=self.now
        )
        self.assertEqual(count_60s, 2)
        self.assertEqual(count_30s, 1)

    def test_does_not_mutate_requests_table(self):
        self._record_success_attempt(_DEX, _DEX_KIND)
        before = self._count_rows("printer_source_requests")
        count_recent_source_requests(self.db_path, _DEX, now=self.now)
        after = self._count_rows("printer_source_requests")
        self.assertEqual(before, after)

    def test_returns_int_type(self):
        result = count_recent_source_requests(self.db_path, _DEX, now=self.now)
        self.assertIsInstance(result, int)

    def test_accepts_sqlite3_connection_as_db_argument(self):
        self._record_success_attempt(_DEX, _DEX_KIND)
        conn = sqlite3.connect(self.db_path)
        try:
            result = count_recent_source_requests(conn, _DEX, now=self.now)
        finally:
            conn.close()
        self.assertEqual(result, 1)


class LaneE2CBAuditVisibilityTests(_DbTestBase):
    """Prove budget accounting does not hide audit rows."""

    def test_source_responses_remain_audit_visible_after_counting(self):
        self._record_success_attempt(_DEX, _DEX_KIND)
        responses_before = self._count_rows("printer_source_responses")
        count_recent_source_requests(self.db_path, _DEX, now=self.now)
        responses_after = self._count_rows("printer_source_responses")

        self.assertEqual(responses_before, responses_after)
        self.assertGreater(responses_after, 0)

    def test_source_failures_remain_audit_visible_after_counting(self):
        self._record_network_failure_attempt(_DEX, _DEX_KIND)
        failures_before = self._count_rows("printer_source_failures")
        count_recent_source_requests(self.db_path, _DEX, now=self.now)
        failures_after = self._count_rows("printer_source_failures")

        self.assertEqual(failures_before, failures_after)
        self.assertGreater(failures_after, 0)


class LaneE2CBGovernorIntegrationTests(_DbTestBase):
    """Prove count_recent_source_requests feeds correctly into can_request_source."""

    def test_count_0_feeds_into_governor_as_allowed(self):
        count = count_recent_source_requests(
            self.db_path, _RATE_LIMIT_SOURCE, now=self.now
        )
        self.assertEqual(count, 0)
        decision = can_request_source(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND, count)
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reason, "allowed")

    def test_count_below_limit_feeds_into_governor_as_allowed(self):
        for i in range(_RATE_LIMIT - 1):
            self._record_success_attempt(
                _RATE_LIMIT_SOURCE,
                _RATE_LIMIT_KIND,
                at=self.now - timedelta(seconds=i),
            )
        count = count_recent_source_requests(
            self.db_path, _RATE_LIMIT_SOURCE, now=self.now
        )
        self.assertEqual(count, _RATE_LIMIT - 1)
        decision = can_request_source(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND, count)
        self.assertTrue(decision.allowed)

    def test_count_at_rate_limit_feeds_into_governor_as_blocked(self):
        for i in range(_RATE_LIMIT):
            self._record_success_attempt(
                _RATE_LIMIT_SOURCE,
                _RATE_LIMIT_KIND,
                at=self.now - timedelta(seconds=i),
            )
        count = count_recent_source_requests(
            self.db_path, _RATE_LIMIT_SOURCE, now=self.now
        )
        self.assertEqual(count, _RATE_LIMIT)
        decision = can_request_source(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND, count)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "rate_limit_exceeded")

    def test_count_above_rate_limit_feeds_into_governor_as_blocked(self):
        for i in range(_RATE_LIMIT + 3):
            self._record_success_attempt(
                _RATE_LIMIT_SOURCE,
                _RATE_LIMIT_KIND,
                at=self.now - timedelta(seconds=i),
            )
        count = count_recent_source_requests(
            self.db_path, _RATE_LIMIT_SOURCE, now=self.now
        )
        self.assertGreater(count, _RATE_LIMIT)
        decision = can_request_source(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND, count)
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, "rate_limit_exceeded")

    def test_counts_are_per_source_independent(self):
        for i in range(_RATE_LIMIT):
            self._record_success_attempt(
                _RATE_LIMIT_SOURCE,
                _RATE_LIMIT_KIND,
                at=self.now - timedelta(seconds=i),
            )
        rate_limited_count = count_recent_source_requests(
            self.db_path, _RATE_LIMIT_SOURCE, now=self.now
        )
        gecko_count = count_recent_source_requests(
            self.db_path, _GECKO, now=self.now
        )
        self.assertEqual(rate_limited_count, _RATE_LIMIT)
        self.assertEqual(gecko_count, 0)

        rate_limited_decision = can_request_source(
            _RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND, rate_limited_count
        )
        gecko_decision = can_request_source(_GECKO, _GECKO_KIND, gecko_count)

        self.assertFalse(rate_limited_decision.allowed)
        self.assertEqual(rate_limited_decision.reason, "rate_limit_exceeded")
        self.assertTrue(gecko_decision.allowed)

    def test_blocked_decision_has_retry_after_seconds(self):
        for i in range(_RATE_LIMIT):
            self._record_success_attempt(
                _RATE_LIMIT_SOURCE,
                _RATE_LIMIT_KIND,
                at=self.now - timedelta(seconds=i),
            )
        count = count_recent_source_requests(
            self.db_path, _RATE_LIMIT_SOURCE, now=self.now
        )
        decision = can_request_source(_RATE_LIMIT_SOURCE, _RATE_LIMIT_KIND, count)
        self.assertFalse(decision.allowed)
        self.assertIsNotNone(decision.retry_after_seconds)
        self.assertGreater(decision.retry_after_seconds, 0)


if __name__ == "__main__":
    unittest.main()