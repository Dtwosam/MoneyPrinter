"""V2-2AG — OBSERVED_LIVE_LAUNCH Tier Implementation Tests.

Fixture-only proof verifying:
  A. pumpportal.py: live_observed_launch flag set for mint-bearing launch
     events with no explicit timestamp fields
  B. pumpportal.py: live_observed_launch NOT set for migration events,
     ack messages, or events that already carry explicit timestamp fields
  C. parser.py: token_age_evidence_tier == "OBSERVED_LIVE_LAUNCH" flows
     through the full pipeline for qualifying candidates
  D. token_created_at and token_age_seconds remain None for OBSERVED_LIVE_LAUNCH
  E. T2 takes precedence when an explicit timestamp is present
  F. Migration events get None tier (never OBSERVED_LIVE_LAUNCH)
  G. A3 does not fire for OBSERVED_LIVE_LAUNCH candidates
  H. Tier survives into candidate metadata via extract_candidate_metadata

Hard rules:
  - T2 = explicit source-provided timestamp only (unchanged)
  - token_created_at never set from captured_at
  - token_age_seconds never computed from captured_at
  - A3 requires token_age_seconds is not None (unchanged)
  - migration events never qualify

No live source calls, no DB mutation, no memory generation, retrieval, paper
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

from printer_v1.discovery.parser import normalize_candidate, normalize_candidates
from printer_v1.discovery.selection_batch import (
    AGE_UNKNOWN,
    BUCKET_A3,
    UNKNOWN_TIER_5,
    assign_bucket,
    derive_age_bucket,
    derive_activity_bucket,
    derive_recent_active_tier,
    extract_candidate_metadata,
    _METADATA_FIELDS,
)
from printer_v1.sources.pumpportal import (
    PUMPPORTAL_SOURCE_NAME,
    _normalize_pumpportal_event,
    normalize_pumpportal_payload,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_FIXED_NOW = datetime(2026, 7, 10, 12, 0, 0, tzinfo=timezone.utc)
_FIXED_NOW_ISO = "2026-07-10T12:00:00+00:00"

_FRESH_CREATED_ISO = (_FIXED_NOW - timedelta(seconds=90)).isoformat()

_MINT = "So11111111111111111111111111111111111111112"
_PAIR = "BondingCurve111111111111111111111111111111111"
_MIG_PAIR = "RaydiumPool111111111111111111111111111111111"


def _launch_event_no_ts(
    *,
    mint: str = _MINT,
    pair: str = _PAIR,
    captured_at: str = _FIXED_NOW_ISO,
) -> dict:
    """A mint-bearing launch event with NO timestamp fields — the V2-2AE payload shape."""
    return {
        "mint": mint,
        "bondingCurveKey": pair,
        "captured_at": captured_at,
        "symbol": "TST",
        "name": "Test Token",
        "liquidity_usd": 5000.0,
        "solAmount": 10.0,
    }


def _launch_event_with_ts(
    *,
    mint: str = _MINT,
    pair: str = _PAIR,
    captured_at: str = _FIXED_NOW_ISO,
    timestamp: str = _FRESH_CREATED_ISO,
) -> dict:
    """A mint-bearing launch event WITH an explicit timestamp field → T2."""
    return {
        "mint": mint,
        "bondingCurveKey": pair,
        "captured_at": captured_at,
        "timestamp": timestamp,
        "symbol": "TST",
        "name": "Test Token",
        "liquidity_usd": 5000.0,
    }


def _migration_event(
    *,
    mint: str = _MINT,
    pair: str = _MIG_PAIR,
    captured_at: str = _FIXED_NOW_ISO,
) -> dict:
    return {
        "mint": mint,
        "newRaydiumPool": pair,
        "captured_at": captured_at,
        "symbol": "TST",
        "name": "Test Token",
        "liquidity_usd": 5000.0,
    }


def _ack_message() -> dict:
    """PumpPortal subscription acknowledgement — no mint."""
    return {"message": "Successfully subscribed to token creation events."}


def _run_launch_pipeline(event: dict, *, now: datetime = _FIXED_NOW) -> dict:
    result = normalize_pumpportal_payload(
        {"events": [event]},
        request_kind="pumpfun_launch_stream",
    )
    assert result.normalized_payload is not None, (
        f"Expected normalized payload, got status={result.source_status}"
    )
    candidates = normalize_candidates(PUMPPORTAL_SOURCE_NAME, result.normalized_payload, now=now)
    assert candidates, "Expected at least one candidate"
    return candidates[0]


def _run_migration_pipeline(event: dict, *, now: datetime = _FIXED_NOW) -> dict:
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


# ---------------------------------------------------------------------------
# A. pumpportal.py: live_observed_launch flag in normalizer output
# ---------------------------------------------------------------------------

class TestPumpPortalNormalizerLiveObservedLaunchFlag(unittest.TestCase):

    def test_mint_bearing_launch_no_ts_sets_flag(self):
        """Mint-bearing launch event with no timestamp fields → live_observed_launch=True."""
        out = _normalize_pumpportal_event(_launch_event_no_ts(), "pumpfun_launch_stream")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("live_observed_launch"),
                        "live_observed_launch must be True when no explicit timestamp exists")

    def test_launch_event_with_ts_does_not_set_flag(self):
        """Launch event with explicit timestamp → live_observed_launch=False (T2 path)."""
        out = _normalize_pumpportal_event(
            _launch_event_with_ts(),
            "pumpfun_launch_stream",
        )
        self.assertIsNotNone(out)
        self.assertFalse(out.get("live_observed_launch"),
                         "live_observed_launch must be False when explicit timestamp is present")

    def test_launch_event_with_tokenCreatedAt_does_not_set_flag(self):
        ev = _launch_event_no_ts()
        ev["tokenCreatedAt"] = _FRESH_CREATED_ISO
        out = _normalize_pumpportal_event(ev, "pumpfun_launch_stream")
        self.assertIsNotNone(out)
        self.assertFalse(out.get("live_observed_launch"))

    def test_launch_event_with_createdTimestamp_does_not_set_flag(self):
        ev = _launch_event_no_ts()
        ev["createdTimestamp"] = _FRESH_CREATED_ISO
        out = _normalize_pumpportal_event(ev, "pumpfun_launch_stream")
        self.assertIsNotNone(out)
        self.assertFalse(out.get("live_observed_launch"))

    def test_migration_event_does_not_set_flag(self):
        """Migration events must never get live_observed_launch=True."""
        out = _normalize_pumpportal_event(_migration_event(), "pumpfun_migration_stream")
        self.assertIsNotNone(out)
        self.assertFalse(out.get("live_observed_launch"),
                         "migration events must never have live_observed_launch=True")

    def test_ack_message_returns_none(self):
        """Subscription acknowledgement (no mint) → normalizer returns None, no flag."""
        out = _normalize_pumpportal_event(_ack_message(), "pumpfun_launch_stream")
        self.assertIsNone(out, "ack message with no mint must not produce a normalized event")

    def test_no_ts_flag_token_created_at_stays_none(self):
        """When live_observed_launch is True, token_created_at must be None."""
        out = _normalize_pumpportal_event(_launch_event_no_ts(), "pumpfun_launch_stream")
        self.assertIsNotNone(out)
        self.assertTrue(out.get("live_observed_launch"))
        self.assertIsNone(out.get("token_created_at"),
                          "token_created_at must remain None when no explicit timestamp exists")


# ---------------------------------------------------------------------------
# B. Full pipeline: token_age_evidence_tier == "OBSERVED_LIVE_LAUNCH"
# ---------------------------------------------------------------------------

class TestObservedLiveLaunchTierFullPipeline(unittest.TestCase):

    def test_tier_is_observed_live_launch_for_no_ts_event(self):
        """Mint-bearing launch event without timestamp → OBSERVED_LIVE_LAUNCH tier."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(
            candidate.get("token_age_evidence_tier"),
            "OBSERVED_LIVE_LAUNCH",
        )

    def test_token_created_at_remains_none(self):
        """token_created_at must be None for OBSERVED_LIVE_LAUNCH candidates."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")
        self.assertIsNone(candidate.get("token_created_at"),
                          "token_created_at must never be populated from captured_at")

    def test_token_age_seconds_remains_none(self):
        """token_age_seconds must be None for OBSERVED_LIVE_LAUNCH candidates."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")
        self.assertIsNone(candidate.get("token_age_seconds"),
                          "token_age_seconds must never be computed from captured_at")

    def test_captured_at_is_populated(self):
        """captured_at must still be recorded (observation time) even for OBSERVED_LIVE_LAUNCH."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")
        self.assertIsNotNone(candidate.get("captured_at"),
                             "captured_at must be present as the observation timestamp")


# ---------------------------------------------------------------------------
# C. T2 takes precedence over OBSERVED_LIVE_LAUNCH
# ---------------------------------------------------------------------------

class TestT2TakesPrecedenceOverObservedLiveLaunch(unittest.TestCase):

    def test_launch_with_timestamp_gets_t2_not_observed_live(self):
        """Launch event WITH explicit timestamp → T2 tier, not OBSERVED_LIVE_LAUNCH."""
        candidate = _run_launch_pipeline(_launch_event_with_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2",
                         "T2 must take precedence when explicit timestamp is present")

    def test_launch_with_timestamp_token_created_at_populated(self):
        """When T2 applies, token_created_at is populated from the event timestamp."""
        candidate = _run_launch_pipeline(_launch_event_with_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")
        self.assertIsNotNone(candidate.get("token_created_at"),
                             "T2 candidates must have token_created_at from event timestamp")

    def test_launch_with_tokenCreatedAt_field_gets_t2(self):
        ev = _launch_event_no_ts()
        ev["tokenCreatedAt"] = _FRESH_CREATED_ISO
        candidate = _run_launch_pipeline(ev)
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")

    def test_launch_with_createdTimestamp_field_gets_t2(self):
        ev = _launch_event_no_ts()
        ev["createdTimestamp"] = _FRESH_CREATED_ISO
        candidate = _run_launch_pipeline(ev)
        self.assertEqual(candidate.get("token_age_evidence_tier"), "T2")


# ---------------------------------------------------------------------------
# D. Migration events: tier must be None, never OBSERVED_LIVE_LAUNCH
# ---------------------------------------------------------------------------

class TestMigrationEventNeverGetsObservedLiveLaunch(unittest.TestCase):

    def test_migration_tier_is_none(self):
        """Migration event → token_age_evidence_tier must be None."""
        candidate = _run_migration_pipeline(_migration_event())
        self.assertIsNone(candidate.get("token_age_evidence_tier"),
                          "migration events must never get OBSERVED_LIVE_LAUNCH tier")

    def test_migration_tier_is_not_observed_live_launch(self):
        """Explicit assertion: migration tier != OBSERVED_LIVE_LAUNCH."""
        candidate = _run_migration_pipeline(_migration_event())
        self.assertNotEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")

    def test_migration_token_created_at_is_none(self):
        """Migration events must not set token_created_at."""
        candidate = _run_migration_pipeline(_migration_event())
        self.assertIsNone(candidate.get("token_created_at"))


# ---------------------------------------------------------------------------
# E. A3 does not fire for OBSERVED_LIVE_LAUNCH candidates
# ---------------------------------------------------------------------------

class TestA3NotUnlockedByObservedLiveLaunch(unittest.TestCase):

    def test_a3_does_not_fire_when_token_age_seconds_is_none(self):
        """A3 requires token_age_seconds is not None — OBSERVED_LIVE_LAUNCH leaves it None."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")
        self.assertIsNone(candidate.get("token_age_seconds"))

        # A3 gate: _tok_age_known = token_age_seconds is not None
        tok_age_known = candidate.get("token_age_seconds") is not None
        self.assertFalse(tok_age_known,
                         "_tok_age_known must be False for OBSERVED_LIVE_LAUNCH candidates")

    def test_age_bucket_is_age_unknown_for_observed_live_launch(self):
        """derive_age_bucket must return AGE_UNKNOWN when token_age_seconds is None."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")
        age_bucket = derive_age_bucket(candidate)
        self.assertEqual(age_bucket, AGE_UNKNOWN)

    def test_assign_bucket_does_not_assign_a3_for_observed_live_launch(self):
        """assign_bucket must not assign A3 for a candidate with OBSERVED_LIVE_LAUNCH tier."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")

        # Build a candidate dict with enough market data to trigger other buckets
        # but missing token_age_seconds — A3 must not fire.
        test_candidate = dict(candidate)
        test_candidate.update({
            "price_change_1h": -50.0,  # would trigger A3 if age known
            "volume_1h": 10_000.0,
            "txns_1h": 100,
            "liquidity_usd": 5_000.0,
        })

        age_bucket = derive_age_bucket(test_candidate)
        activity_bucket = derive_activity_bucket(test_candidate)
        tier = derive_recent_active_tier(age_bucket, activity_bucket)

        self.assertNotEqual(tier, BUCKET_A3,
                            "OBSERVED_LIVE_LAUNCH must not unlock A3")
        self.assertEqual(tier, UNKNOWN_TIER_5,
                         "Without token_age_seconds, tier must remain T5 unknown")


# ---------------------------------------------------------------------------
# F. Tier survives into candidate metadata
# ---------------------------------------------------------------------------

class TestObservedLiveLaunchTierSurvivesToMetadata(unittest.TestCase):

    def test_tier_in_metadata_fields_constant(self):
        """token_age_evidence_tier must be in _METADATA_FIELDS."""
        self.assertIn("token_age_evidence_tier", _METADATA_FIELDS)

    def test_observed_live_launch_tier_in_extract_candidate_metadata(self):
        """extract_candidate_metadata must carry OBSERVED_LIVE_LAUNCH value."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        self.assertEqual(candidate.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")

        meta = extract_candidate_metadata(candidate)
        self.assertIn("token_age_evidence_tier", meta)
        self.assertEqual(meta["token_age_evidence_tier"], "OBSERVED_LIVE_LAUNCH")

    def test_token_created_at_in_metadata_is_none(self):
        """token_created_at must be None in metadata for OBSERVED_LIVE_LAUNCH candidates."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        meta = extract_candidate_metadata(candidate)
        self.assertIsNone(meta.get("token_created_at"))

    def test_token_age_seconds_in_metadata_is_none(self):
        """token_age_seconds must be None in metadata for OBSERVED_LIVE_LAUNCH candidates."""
        candidate = _run_launch_pipeline(_launch_event_no_ts())
        meta = extract_candidate_metadata(candidate)
        self.assertIsNone(meta.get("token_age_seconds"))


# ---------------------------------------------------------------------------
# G. Normalizer-level direct unit tests for _derive_token_age_evidence_tier
# ---------------------------------------------------------------------------

class TestDeriveTokenAgeEvidenceTierDirectly(unittest.TestCase):
    """Direct unit tests on the parser function via normalize_candidate."""

    def _make_pumpportal_candidate(
        self,
        *,
        token_created_at: str | None = None,
        live_observed_launch: bool = False,
        request_kind: str = "pumpfun_launch_stream",
    ) -> dict:
        return {
            "mint": _MINT,
            "token_mint": _MINT,
            "bondingCurveKey": _PAIR,
            "pair_address": _PAIR,
            "pairAddress": _PAIR,
            "chain": "solana",
            "source_name": PUMPPORTAL_SOURCE_NAME,
            "request_kind": request_kind,
            "captured_at": _FIXED_NOW_ISO,
            "token_created_at": token_created_at,
            "live_observed_launch": live_observed_launch,
            "dex": "pumpfun",
            "poolSource": PUMPPORTAL_SOURCE_NAME,
            "symbol": "TST",
            "name": "Test Token",
            "liquidity_usd": 5000.0,
            "price_usd": "0.001",
        }

    def test_observed_live_launch_flag_true_produces_tier(self):
        payload = self._make_pumpportal_candidate(live_observed_launch=True)
        result = normalize_candidate(PUMPPORTAL_SOURCE_NAME, payload, now=_FIXED_NOW)
        self.assertEqual(result.get("token_age_evidence_tier"), "OBSERVED_LIVE_LAUNCH")

    def test_no_flag_no_ts_produces_none_tier(self):
        payload = self._make_pumpportal_candidate(live_observed_launch=False)
        result = normalize_candidate(PUMPPORTAL_SOURCE_NAME, payload, now=_FIXED_NOW)
        self.assertIsNone(result.get("token_age_evidence_tier"))

    def test_t2_present_flag_true_still_gives_t2(self):
        """T2 takes precedence: if token_created_at is set, T2 is returned even if flag is True."""
        payload = self._make_pumpportal_candidate(
            token_created_at=_FRESH_CREATED_ISO,
            live_observed_launch=True,  # flag would normally trigger OBSERVED_LIVE_LAUNCH
        )
        result = normalize_candidate(PUMPPORTAL_SOURCE_NAME, payload, now=_FIXED_NOW)
        self.assertEqual(result.get("token_age_evidence_tier"), "T2",
                         "T2 must take precedence over OBSERVED_LIVE_LAUNCH")

    def test_migration_request_kind_with_flag_gives_none(self):
        """Migration request_kind prevents tier even if live_observed_launch=True."""
        payload = self._make_pumpportal_candidate(
            request_kind="pumpfun_migration_stream",
            live_observed_launch=True,
        )
        result = normalize_candidate(PUMPPORTAL_SOURCE_NAME, payload, now=_FIXED_NOW)
        self.assertIsNone(result.get("token_age_evidence_tier"))

    def test_non_pumpportal_source_with_flag_gives_none(self):
        """Non-pumpportal source always returns None tier."""
        payload = self._make_pumpportal_candidate(live_observed_launch=True)
        result = normalize_candidate("geckoterminal", payload, now=_FIXED_NOW)
        self.assertIsNone(result.get("token_age_evidence_tier"))


if __name__ == "__main__":
    unittest.main()
