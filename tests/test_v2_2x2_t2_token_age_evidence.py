"""V2-2X.2 — T2 Token-Age Evidence Implementation and Fixture Proof.

Fixture-only tests proving:
  A. _parse_event_ts helper parses timestamps correctly
  B. _extract_launch_timestamp validates and rejects correctly
  C. T2 timestamp priority mapping (tokenCreatedAt > createdTimestamp > timestamp)
  D. Invalid timestamp rejection (missing, zero, negative, unparseable, future, stale)
  E. Migration events hard-blocked from T2 tier
  F. Pair-age isolation (pair age never assigned to token age, A3, recent-active tier)
  G. A3 behavior with and without T2 evidence
  H. Metadata survival (tier and pair_age_context_label through selection batch)
  I. Safety (no live source calls, no source infra rows)

No live source fetching, DB mutation, memory generation, retrieval, paper
decisions, BUY/SELL/HOLD, positions, trades, audits, PnL, scheduler, runtime,
scoring, ranking, confidence, weighted logic, embeddings, or vectors.
"""

from __future__ import annotations

import pathlib
import sys
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.discovery.parser import NORMALIZED_FIELDS, normalize_candidate, normalize_candidates
from printer_v1.discovery.selection_batch import (
    AGE_UNKNOWN,
    BUCKET_A1,
    BUCKET_A3,
    UNKNOWN_TIER_5,
    assign_bucket,
    derive_age_bucket,
    derive_activity_bucket,
    derive_recent_active_tier,
    extract_candidate_metadata,
)
from printer_v1.sources.pumpportal import (
    PUMPPORTAL_SOURCE_NAME,
    _extract_launch_timestamp,
    _parse_event_ts,
    build_pumpportal_adapter,
    fixture_success_transport,
    normalize_pumpportal_payload,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# Normalization reference time used by parser (substitutes datetime.now())
_FIXED_NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)
_FIXED_NOW_ISO = "2026-07-09T12:00:00+00:00"

# Token created 2 minutes before _FIXED_NOW; captured right at _FIXED_NOW.
# Staleness at capture: 120s → valid.  token_age_seconds at _FIXED_NOW: 120s.
_FRESH_CREATED_ISO = (_FIXED_NOW - timedelta(seconds=120)).isoformat()

# Token created at 09:00; captured 1 minute later at 09:01.
# Staleness at capture: 60s → valid.  token_age_seconds at _FIXED_NOW: 10 800s.
_OLD_TOKEN_CREATED_ISO = "2026-07-09T09:00:00+00:00"
_OLD_TOKEN_CAPTURED_ISO = "2026-07-09T09:01:00+00:00"

# Boundary: exactly 3600s staleness (captured_at = _FIXED_NOW, created = 3600s earlier).
# Staleness = 3600.0 → NOT stale (threshold is strictly > 3600).
_BOUNDARY_CREATED_ISO = (_FIXED_NOW - timedelta(seconds=3600)).isoformat()

# Stale: 3601s before _FIXED_NOW → rejected.
_STALE_CREATED_ISO = (_FIXED_NOW - timedelta(seconds=3601)).isoformat()

# Future timestamp → rejected.
_FUTURE_CREATED_ISO = (_FIXED_NOW + timedelta(hours=1)).isoformat()

# Epoch values for numeric timestamp tests.
_FRESH_CREATED_EPOCH_S = int((_FIXED_NOW - timedelta(seconds=120)).timestamp())
_FRESH_CREATED_EPOCH_MS = _FRESH_CREATED_EPOCH_S * 1000


# ---------------------------------------------------------------------------
# Pipeline helpers
# ---------------------------------------------------------------------------

def _run_launch_pipeline(
    event: dict,
    *,
    now: datetime = _FIXED_NOW,
) -> dict:
    """Full pipeline: pumpportal events path → parser normalization."""
    result = normalize_pumpportal_payload(
        {"events": [event]},
        request_kind="pumpfun_launch_stream",
    )
    assert result.normalized_payload is not None, (
        f"Expected normalized payload, got status={result.source_status}"
    )
    candidates = normalize_candidates(PUMPPORTAL_SOURCE_NAME, result.normalized_payload, now=now)
    assert candidates, "Expected at least one candidate from launch event"
    return candidates[0]


def _run_migration_pipeline(
    event: dict,
    *,
    now: datetime = _FIXED_NOW,
) -> dict:
    """Full pipeline for migration events."""
    result = normalize_pumpportal_payload(
        {"events": [event]},
        request_kind="pumpfun_migration_stream",
    )
    assert result.normalized_payload is not None, (
        f"Expected normalized payload, got status={result.source_status}"
    )
    candidates = normalize_candidates(PUMPPORTAL_SOURCE_NAME, result.normalized_payload, now=now)
    assert candidates, "Expected at least one candidate from migration event"
    return candidates[0]


def _launch_event(
    *,
    mint: str = "MINT_LAUNCH_T2",
    pair: str = "PAIR_LAUNCH_T2",
    captured_at: str = _FIXED_NOW_ISO,
    tokenCreatedAt: str | int | None = None,
    createdTimestamp: str | int | None = None,
    timestamp: str | int | None = None,
    liquidity_usd: float = 8_000.0,
    volume_5m: float = 2_000.0,
    txns_5m: int = 20,
    price_change_1h: float | None = None,
) -> dict:
    d: dict = {
        "mint": mint,
        "bondingCurveKey": pair,
        "captured_at": captured_at,
        "liquidity_usd": liquidity_usd,
        "volume_5m": volume_5m,
        "txns_5m": txns_5m,
        "symbol": "TST",
        "name": "Test Token",
    }
    if tokenCreatedAt is not None:
        d["tokenCreatedAt"] = tokenCreatedAt
    if createdTimestamp is not None:
        d["createdTimestamp"] = createdTimestamp
    if timestamp is not None:
        d["timestamp"] = timestamp
    if price_change_1h is not None:
        d["price_change_1h"] = price_change_1h
    return d


def _migration_event(
    *,
    mint: str = "MINT_MIG_T2",
    pair: str = "PAIR_MIG_T2_NEW",
    captured_at: str = _FIXED_NOW_ISO,
    timestamp: str | None = _FRESH_CREATED_ISO,
    tokenCreatedAt: str | None = None,
) -> dict:
    d: dict = {
        "mint": mint,
        "newRaydiumPool": pair,
        "captured_at": captured_at,
        "liquidity_usd": 8_000.0,
        "volume_5m": 2_000.0,
        "txns_5m": 20,
        "symbol": "TST",
        "name": "Test Migration Token",
    }
    if timestamp is not None:
        d["timestamp"] = timestamp
    if tokenCreatedAt is not None:
        d["tokenCreatedAt"] = tokenCreatedAt
    return d


# ---------------------------------------------------------------------------
# A. _parse_event_ts unit tests
# ---------------------------------------------------------------------------

class TestParseEventTs(unittest.TestCase):
    def test_none_returns_none(self):
        self.assertIsNone(_parse_event_ts(None))

    def test_empty_string_returns_none(self):
        self.assertIsNone(_parse_event_ts(""))

    def test_zero_int_returns_none(self):
        self.assertIsNone(_parse_event_ts(0))

    def test_zero_float_returns_none(self):
        self.assertIsNone(_parse_event_ts(0.0))

    def test_negative_int_returns_none(self):
        self.assertIsNone(_parse_event_ts(-100))

    def test_negative_float_returns_none(self):
        self.assertIsNone(_parse_event_ts(-1.5))

    def test_valid_epoch_seconds(self):
        # 2026-07-09T12:00:00Z in epoch seconds
        epoch_s = int(_FIXED_NOW.timestamp())
        result = _parse_event_ts(epoch_s)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertEqual(result.tzinfo, timezone.utc)
        # Should round-trip to within 1 second
        self.assertAlmostEqual(result.timestamp(), _FIXED_NOW.timestamp(), delta=1.0)

    def test_valid_epoch_milliseconds(self):
        epoch_ms = int(_FIXED_NOW.timestamp()) * 1000
        result = _parse_event_ts(epoch_ms)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.timestamp(), _FIXED_NOW.timestamp(), delta=1.0)

    def test_valid_iso_string(self):
        result = _parse_event_ts(_FIXED_NOW_ISO)
        self.assertIsNotNone(result)
        assert result is not None
        self.assertAlmostEqual(result.timestamp(), _FIXED_NOW.timestamp(), delta=1.0)

    def test_valid_iso_string_z_suffix(self):
        iso_z = _FIXED_NOW_ISO.replace("+00:00", "Z")
        result = _parse_event_ts(iso_z)
        self.assertIsNotNone(result)

    def test_unparseable_string_returns_none(self):
        self.assertIsNone(_parse_event_ts("not-a-date"))

    def test_list_returns_none(self):
        self.assertIsNone(_parse_event_ts([1234567890]))


# ---------------------------------------------------------------------------
# B. _extract_launch_timestamp unit tests
# ---------------------------------------------------------------------------

class TestExtractLaunchTimestamp(unittest.TestCase):
    def test_tokenCreatedAt_priority_valid(self):
        event = {
            "tokenCreatedAt": _FRESH_CREATED_ISO,
            "createdTimestamp": _STALE_CREATED_ISO,  # would be stale, but lower priority
            "timestamp": _STALE_CREATED_ISO,
        }
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        # Should use tokenCreatedAt (highest priority), which is fresh
        self.assertIsNotNone(result)

    def test_createdTimestamp_fallback(self):
        event = {"createdTimestamp": _FRESH_CREATED_ISO, "timestamp": _STALE_CREATED_ISO}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNotNone(result)

    def test_timestamp_last_resort(self):
        event = {"timestamp": _FRESH_CREATED_ISO}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNotNone(result)

    def test_all_fields_absent_returns_none(self):
        result = _extract_launch_timestamp({}, _FIXED_NOW_ISO)
        self.assertIsNone(result)

    def test_zero_tokenCreatedAt_rejected(self):
        event = {"tokenCreatedAt": 0}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNone(result)

    def test_negative_unix_rejected(self):
        event = {"tokenCreatedAt": -1000}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNone(result)

    def test_unparseable_string_rejected(self):
        event = {"tokenCreatedAt": "not-a-date"}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNone(result)

    def test_future_timestamp_rejected(self):
        event = {"tokenCreatedAt": _FUTURE_CREATED_ISO}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNone(result)

    def test_stale_over_3600s_rejected(self):
        event = {"tokenCreatedAt": _STALE_CREATED_ISO}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNone(result)

    def test_boundary_exactly_3600s_accepted(self):
        event = {"tokenCreatedAt": _BOUNDARY_CREATED_ISO}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        # Staleness = 3600.0 exactly; threshold is strictly > 3600 → accepted
        self.assertIsNotNone(result)

    def test_valid_epoch_ms_accepted(self):
        event = {"tokenCreatedAt": _FRESH_CREATED_EPOCH_MS}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNotNone(result)

    def test_valid_epoch_s_accepted(self):
        event = {"tokenCreatedAt": _FRESH_CREATED_EPOCH_S}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNotNone(result)

    def test_result_is_iso_string(self):
        event = {"tokenCreatedAt": _FRESH_CREATED_ISO}
        result = _extract_launch_timestamp(event, _FIXED_NOW_ISO)
        self.assertIsNotNone(result)
        assert result is not None
        # Should be parseable as ISO-8601
        dt = datetime.fromisoformat(result.replace("Z", "+00:00"))
        self.assertIsNotNone(dt)


# ---------------------------------------------------------------------------
# C. Full pipeline: T2 priority field mapping
# ---------------------------------------------------------------------------

class TestT2TimestampMapping(unittest.TestCase):
    def test_tokenCreatedAt_maps_to_token_created_at(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertIsNotNone(candidate.get("token_created_at"))

    def test_createdTimestamp_maps_to_token_created_at(self):
        event = _launch_event(createdTimestamp=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertIsNotNone(candidate.get("token_created_at"))

    def test_timestamp_field_maps_to_token_created_at(self):
        event = _launch_event(timestamp=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertIsNotNone(candidate.get("token_created_at"))

    def test_token_age_seconds_derived_from_t2(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        age = candidate.get("token_age_seconds")
        self.assertIsNotNone(age)
        # token_age_seconds ≈ 120s (2 minutes)
        assert age is not None
        self.assertAlmostEqual(float(age), 120.0, delta=5.0)

    def test_t2_tier_stamped_for_launch(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")

    def test_tokenCreatedAt_takes_priority_over_timestamp(self):
        # tokenCreatedAt is fresh; timestamp would be stale if used
        event = _launch_event(
            tokenCreatedAt=_FRESH_CREATED_ISO,
            timestamp=_STALE_CREATED_ISO,
        )
        candidate = _run_launch_pipeline(event)
        # Should succeed using tokenCreatedAt, not fall through to stale timestamp
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")

    def test_epoch_ms_tokenCreatedAt_accepted(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_EPOCH_MS)
        candidate = _run_launch_pipeline(event)
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")
        self.assertIsNotNone(candidate.get("token_age_seconds"))

    def test_epoch_s_tokenCreatedAt_accepted(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_EPOCH_S)
        candidate = _run_launch_pipeline(event)
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")


# ---------------------------------------------------------------------------
# D. Full pipeline: invalid timestamp rejection
# ---------------------------------------------------------------------------

class TestT2InvalidTimestamps(unittest.TestCase):
    def test_no_timestamp_fields_no_t2(self):
        event = _launch_event()  # no tokenCreatedAt, createdTimestamp, or timestamp
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_created_at"))
        self.assertIsNone(candidate.get("token_age_seconds"))
        self.assertIsNone(candidate.get("token_age_evidence_tier"))

    def test_zero_tokenCreatedAt_no_t2(self):
        event = _launch_event(tokenCreatedAt=0)
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))

    def test_negative_unix_no_t2(self):
        event = _launch_event(tokenCreatedAt=-1000)
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))

    def test_unparseable_string_no_t2(self):
        event = _launch_event(tokenCreatedAt="not-a-real-date")
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))

    def test_future_timestamp_no_t2(self):
        event = _launch_event(tokenCreatedAt=_FUTURE_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))

    def test_stale_over_3600s_no_t2(self):
        event = _launch_event(tokenCreatedAt=_STALE_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))
        self.assertIsNone(candidate.get("token_created_at"))

    def test_boundary_exactly_3600s_accepted(self):
        event = _launch_event(tokenCreatedAt=_BOUNDARY_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        # 3600s exactly is NOT stale (strictly > 3600 check)
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")

    def test_stale_one_second_over_no_t2(self):
        event = _launch_event(tokenCreatedAt=_STALE_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))

    def test_empty_string_tokenCreatedAt_no_t2(self):
        event = _launch_event()
        event["tokenCreatedAt"] = ""
        candidate = _run_launch_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))


# ---------------------------------------------------------------------------
# E. Migration events hard-blocked from T2
# ---------------------------------------------------------------------------

class TestMigrationHardBlock(unittest.TestCase):
    def test_migration_no_token_created_at(self):
        event = _migration_event()
        candidate = _run_migration_pipeline(event)
        self.assertIsNone(candidate.get("token_created_at"))

    def test_migration_no_token_age_evidence_tier(self):
        event = _migration_event()
        candidate = _run_migration_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))

    def test_migration_with_fresh_timestamp_still_no_t2(self):
        # Even if the migration event has a fresh timestamp field, it should
        # never produce T2 evidence (migration time ≠ token creation time)
        event = _migration_event(timestamp=_FRESH_CREATED_ISO)
        candidate = _run_migration_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))
        self.assertIsNone(candidate.get("token_created_at"))

    def test_migration_with_tokenCreatedAt_still_no_t2(self):
        event = _migration_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_migration_pipeline(event)
        self.assertIsNone(candidate.get("token_age_evidence_tier"))
        self.assertIsNone(candidate.get("token_created_at"))

    def test_migration_no_token_age_seconds(self):
        event = _migration_event(timestamp=_FRESH_CREATED_ISO)
        candidate = _run_migration_pipeline(event)
        self.assertIsNone(candidate.get("token_age_seconds"))

    def test_migration_pair_address_present(self):
        event = _migration_event(pair="PAIR_MIG_RAYDIUM")
        candidate = _run_migration_pipeline(event)
        self.assertIsNotNone(candidate.get("pair_address"))


# ---------------------------------------------------------------------------
# F. Pair-age isolation
# ---------------------------------------------------------------------------

class TestPairAgeIsolation(unittest.TestCase):
    def _pair_only_candidate(self) -> dict:
        """Build a candidate with pair age but no token age (flat normalized dict)."""
        return normalize_candidate(
            "geckoterminal",
            {
                "token_mint": "MINT_PAIRONLY_111",
                "pair_address": "PAIR_PAIRONLY_111",
                "chain": "solana",
                "captured_at": _FIXED_NOW_ISO,
                "price_usd": "0.001",
                "liquidity_usd": 8_000.0,
                "volume_5m": 2_000.0,
                "txns_5m": 20,
                "volume_1h": 5_000.0,
                "txns_1h": 50,
                "volume_24h": 20_000.0,
                "txns_24h": 200,
                # pair age present (T4) but no token_created_at
                "pair_created_at": (_FIXED_NOW - timedelta(hours=2)).isoformat(),
            },
            now=_FIXED_NOW,
        )

    def test_pair_age_seconds_present(self):
        c = self._pair_only_candidate()
        self.assertIsNotNone(c.get("pair_age_seconds"))

    def test_token_age_seconds_absent(self):
        c = self._pair_only_candidate()
        self.assertIsNone(c.get("token_age_seconds"))

    def test_pair_age_not_assigned_to_token_age(self):
        c = self._pair_only_candidate()
        pair_age = c.get("pair_age_seconds")
        token_age = c.get("token_age_seconds")
        self.assertIsNotNone(pair_age)
        self.assertIsNone(token_age)
        # Explicit: pair_age must NOT equal token_age (or token_age must be None)
        self.assertNotEqual(pair_age, token_age)

    def test_derive_age_bucket_pair_only_returns_unknown(self):
        c = self._pair_only_candidate()
        self.assertIsNone(c.get("token_age_seconds"))
        age_bucket = derive_age_bucket(c)
        self.assertEqual(age_bucket, AGE_UNKNOWN)

    def test_pair_age_alone_does_not_unlock_recent_active_tier(self):
        c = self._pair_only_candidate()
        age_bucket = derive_age_bucket(c)
        activity_bucket = derive_activity_bucket(c)
        tier = derive_recent_active_tier(age_bucket, activity_bucket)
        # Without real token age, age_bucket = AGE_UNKNOWN → UNKNOWN_TIER_5
        self.assertEqual(tier, UNKNOWN_TIER_5)

    def test_pair_age_alone_does_not_unlock_a3(self):
        # Fast-tier candidate with pair age but no token age → A1, not A3
        c = self._pair_only_candidate()
        # Inject price_change_1h to ensure A3 conditions could theoretically be met
        c = dict(c)
        c["price_change_1h"] = -10.0
        bucket_id, _ = assign_bucket(c)
        # Without token_age_seconds, _tok_age_known=False → not A3
        self.assertNotEqual(bucket_id, BUCKET_A3)

    def test_token_age_evidence_tier_absent_for_pair_only(self):
        c = self._pair_only_candidate()
        self.assertIsNone(c.get("token_age_evidence_tier"))


# ---------------------------------------------------------------------------
# G. A3 behavior
# ---------------------------------------------------------------------------

class TestA3Behavior(unittest.TestCase):
    def _a3_candidate_with_t2(self) -> dict:
        """Launch event where the token is > 1 hour old at normalization time.

        PumpPortal raw events only carry liquidity. Volume/txn/price fields are
        injected into the token dict to simulate what a full discovery pipeline
        would add from additional source enrichment.
        """
        event = _launch_event(
            mint="MINT_A3_T2",
            pair="PAIR_A3_T2",
            captured_at=_OLD_TOKEN_CAPTURED_ISO,  # captured 1 min after creation
            tokenCreatedAt=_OLD_TOKEN_CREATED_ISO,  # created 3 hours before _FIXED_NOW
            liquidity_usd=8_000.0,
        )
        result = normalize_pumpportal_payload(
            {"events": [event]},
            request_kind="pumpfun_launch_stream",
        )
        assert result.normalized_payload is not None
        tokens = list(result.normalized_payload["tokens"])
        token = dict(tokens[0])
        # Inject fast-tier market data (not in raw pumpportal launch events)
        token["volume_5m"] = 2_000.0
        token["txns_5m"] = 20
        token["volume_1h"] = 5_000.0
        token["txns_1h"] = 50
        token["volume_24h"] = 20_000.0
        token["txns_24h"] = 200
        token["price_change_1h"] = -5.0
        return normalize_candidate(PUMPPORTAL_SOURCE_NAME, token, now=_FIXED_NOW)

    def test_a3_fires_with_t2_age_and_price_change(self):
        c = self._a3_candidate_with_t2()
        # Confirm T2 is stamped
        self.assertEqual(c.get("token_age_evidence_tier"), "T2")
        # Confirm token_age_seconds is large enough for A3 (>= 3600s)
        age = c.get("token_age_seconds")
        self.assertIsNotNone(age)
        assert age is not None
        self.assertGreaterEqual(float(age), 3600.0)
        # Assign bucket
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_A3)

    def test_a3_blocked_without_token_age(self):
        # Same fast-tier candidate but no token_age_seconds → A1, not A3
        c: dict = {
            "chain": "solana",
            "token_mint": "MINT_NO_AGE",
            "pair_address": "PAIR_NO_AGE",
            "liquidity_usd": 8_000.0,
            "volume_5m": 2_000.0,
            "txns_5m": 20,
            "price_change_1h": -5.0,
            "token_age_seconds": None,
        }
        bucket_id, _ = assign_bucket(c)
        self.assertNotEqual(bucket_id, BUCKET_A3)

    def test_a3_blocked_without_price_change_1h(self):
        c = self._a3_candidate_with_t2()
        c = dict(c)
        c["price_change_1h"] = None
        bucket_id, _ = assign_bucket(c)
        self.assertNotEqual(bucket_id, BUCKET_A3)

    def test_a3_blocked_without_negative_price_change(self):
        c = self._a3_candidate_with_t2()
        c = dict(c)
        c["price_change_1h"] = 5.0  # positive, not negative
        bucket_id, _ = assign_bucket(c)
        self.assertNotEqual(bucket_id, BUCKET_A3)

    def test_launch_with_young_token_not_a3(self):
        # Token 2 minutes old → age < 3600s → not A3 → A1
        event = _launch_event(
            tokenCreatedAt=_FRESH_CREATED_ISO,
            liquidity_usd=8_000.0,
        )
        result = normalize_pumpportal_payload(
            {"events": [event]},
            request_kind="pumpfun_launch_stream",
        )
        assert result.normalized_payload is not None
        tokens = list(result.normalized_payload["tokens"])
        token = dict(tokens[0])
        # Inject fast-tier market data
        token["volume_5m"] = 2_000.0
        token["txns_5m"] = 20
        token["volume_1h"] = 5_000.0
        token["txns_1h"] = 50
        token["volume_24h"] = 20_000.0
        token["txns_24h"] = 200
        token["price_change_1h"] = -5.0
        c = normalize_candidate(PUMPPORTAL_SOURCE_NAME, token, now=_FIXED_NOW)
        self.assertEqual(c.get("token_age_evidence_tier"), "T2")
        age = c.get("token_age_seconds")
        self.assertIsNotNone(age)
        assert age is not None
        self.assertLess(float(age), 3600.0)
        bucket_id, _ = assign_bucket(c)
        self.assertEqual(bucket_id, BUCKET_A1)  # Not A3 because token too young


# ---------------------------------------------------------------------------
# H. Metadata survival
# ---------------------------------------------------------------------------

class TestMetadataSurvival(unittest.TestCase):
    def test_token_age_evidence_tier_in_normalized_fields(self):
        self.assertIn("token_age_evidence_tier", NORMALIZED_FIELDS)

    def test_pair_age_context_label_in_normalized_fields(self):
        self.assertIn("pair_age_context_label", NORMALIZED_FIELDS)

    def test_request_kind_not_in_normalized_output(self):
        # request_kind is internal to pumpportal token dict but must not appear
        # in the final normalized candidate (not in NORMALIZED_FIELDS)
        self.assertNotIn("request_kind", NORMALIZED_FIELDS)
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertNotIn("request_kind", candidate)

    def test_t2_tier_survives_to_metadata_extraction(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        meta = extract_candidate_metadata(candidate)
        self.assertEqual(meta.get("token_age_evidence_tier"), "T2")

    def test_pair_age_context_label_separate_from_tier(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        meta = extract_candidate_metadata(candidate)
        # Both fields present but independent
        self.assertIn("pair_age_context_label", meta)
        self.assertIn("token_age_evidence_tier", meta)
        self.assertIsNotNone(meta.get("pair_age_context_label"))
        self.assertEqual(meta.get("token_age_evidence_tier"), "T2")

    def test_no_t2_candidate_has_none_tier_in_metadata(self):
        event = _launch_event()  # no timestamp fields
        candidate = _run_launch_pipeline(event)
        meta = extract_candidate_metadata(candidate)
        self.assertIsNone(meta.get("token_age_evidence_tier"))

    def test_token_age_evidence_tier_in_metadata_fields(self):
        # Confirm extract_candidate_metadata covers token_age_evidence_tier
        from printer_v1.discovery.selection_batch import _METADATA_FIELDS
        self.assertIn("token_age_evidence_tier", _METADATA_FIELDS)

    def test_pair_age_context_label_in_metadata_fields(self):
        from printer_v1.discovery.selection_batch import _METADATA_FIELDS
        self.assertIn("pair_age_context_label", _METADATA_FIELDS)

    def test_token_created_at_survives_to_metadata(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        meta = extract_candidate_metadata(candidate)
        self.assertIsNotNone(meta.get("token_created_at"))

    def test_token_age_seconds_survives_to_metadata(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        meta = extract_candidate_metadata(candidate)
        self.assertIsNotNone(meta.get("token_age_seconds"))

    def test_pair_age_context_label_recent_launch_with_t2(self):
        # Token created 2 minutes ago → pair_age_context_label should be RECENT_LAUNCH
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertEqual(candidate.get("pair_age_context_label"), "RECENT_LAUNCH")

    def test_source_name_pumpportal_in_candidate(self):
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        candidate = _run_launch_pipeline(event)
        self.assertEqual(candidate.get("source_name"), PUMPPORTAL_SOURCE_NAME)


# ---------------------------------------------------------------------------
# I. Safety: no live source calls, no source infra rows
# ---------------------------------------------------------------------------

class TestSafety(unittest.TestCase):
    def test_adapter_disabled_by_default(self):
        adapter = build_pumpportal_adapter()
        self.assertFalse(adapter.enabled)
        self.assertEqual(adapter.call_count, 0)

    def test_adapter_fixture_transport_only_metadata(self):
        adapter = build_pumpportal_adapter()
        self.assertTrue(adapter.metadata.fixture_transport_only)
        self.assertFalse(adapter.metadata.supports_network_execution)

    def test_adapter_no_transport_by_default(self):
        adapter = build_pumpportal_adapter()
        self.assertIsNone(adapter.transport)

    def test_normalize_pumpportal_payload_pure_function(self):
        # normalize_pumpportal_payload needs no transport, no DB, no HTTP
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        result = normalize_pumpportal_payload(
            {"events": [event]},
            request_kind="pumpfun_launch_stream",
        )
        self.assertIsNotNone(result.normalized_payload)
        tokens = result.normalized_payload["tokens"]
        self.assertEqual(len(tokens), 1)

    def test_normalize_candidate_pure_function(self):
        # normalize_candidate needs no IO: pure dict transformation
        token = {
            "chain": "solana",
            "mint": "MINT_SAFE_TEST",
            "bondingCurveKey": "PAIR_SAFE_TEST",
            "request_kind": "pumpfun_launch_stream",
            "token_created_at": _FRESH_CREATED_ISO,
            "poolSource": "pumpportal",
            "dex": "pumpfun",
            "liquidity_usd": 8_000.0,
            "captured_at": _FIXED_NOW_ISO,
        }
        candidate = normalize_candidate(PUMPPORTAL_SOURCE_NAME, token, now=_FIXED_NOW)
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")

    def test_adapter_requires_governor_context(self):
        adapter = build_pumpportal_adapter()
        self.assertTrue(adapter.metadata.requires_governor_context)

    def test_fixture_transport_call_not_invoked_without_execute(self):
        call_log: list[int] = []

        def counting_transport(ctx):
            del ctx
            call_log.append(1)
            return {"events": [_launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)]}

        adapter = build_pumpportal_adapter(enabled=True, fixture_transport=counting_transport)
        # Building the adapter does NOT call the transport
        self.assertEqual(adapter.call_count, 0)
        self.assertEqual(len(call_log), 0)

    def test_disallowed_request_kind_fails_safely(self):
        result = normalize_pumpportal_payload(
            {"events": []},
            request_kind="subscribeTokenTrade",  # metered/disallowed
        )
        # normalized_payload defaults to {} on failure; check failure_type instead
        self.assertIsNotNone(result.failure_type)
        self.assertFalse(bool(result.normalized_payload))

    def test_failure_payload_produces_failure_result(self):
        result = normalize_pumpportal_payload(
            {"fixture_status": "failure", "failure_type": "test_failure", "failure_message": "test"},
            request_kind="pumpfun_launch_stream",
        )
        self.assertIsNotNone(result.failure_type)
        self.assertFalse(bool(result.normalized_payload))

    def test_t2_pipeline_produces_no_source_request_rows(self):
        # Full T2 pipeline through normalize functions: entirely in-memory
        event = _launch_event(tokenCreatedAt=_FRESH_CREATED_ISO)
        result = normalize_pumpportal_payload({"events": [event]}, request_kind="pumpfun_launch_stream")
        # NormalizedSourceResult has no db_rows, source_requests, or scheduler_jobs attributes
        self.assertFalse(hasattr(result, "source_request_id"))
        self.assertFalse(hasattr(result, "scheduler_job_id"))
        self.assertFalse(hasattr(result, "memory_window_id"))


if __name__ == "__main__":
    unittest.main()
