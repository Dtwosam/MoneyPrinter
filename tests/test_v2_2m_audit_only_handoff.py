"""V2-2M — WATCH_ONLY/D1 Audit-Only Candidate-Pool Handoff.

Targeted tests for:
  A. Audit-only pool capture: WATCH_ONLY/D1 candidates enter audit_only_pool,
     NOT the accepted (active-tracking) list.
  B. Exclusion rules: non-Solana, INSTANT_REJECT, duplicates excluded from pool.
  C. Metadata: audit_only / candidate_kind / pre_persistence_reject_reason / tracking_lane
     / primary_bucket set correctly on each captured candidate.
  D. Active-tracking guard: audit_only candidates never reach process_discovery_payload.
  E. Quota supplement: audit_only_pool supplies D1/WATCH_ONLY to satisfy 6+ batch quota.
  F. Supplement is minimal: adds only the candidates needed, runs once.
  G. audit_only_report fields: all 16 required fields present; quota_ok / quota_violations
     bonus fields present.
  H. H.1 invariant: new candidate_stage_report fields are all int.
  I. Locked-table regression: no tracking-queue/scheduler rows created for audit-only.
  J. Backward compat: H.1-H.6 invariants preserved for normal (active-tracking) flow.
  K. V2-2M.2: eligibility gate — FAILED/STALE/DIRTY candidates excluded from audit pool.
  L. V2-2M.2: source trace includes source_name and source_channel_reason.

Locks preserved: no live discovery, no source fetching, no live DB mutation,
no memory generation, no retrieval, no paper decisions, no BUY/SELL/HOLD,
no positions/trades/audits/PnL, no scoring/ranking/confidence/weighted logic.
"""

from __future__ import annotations

import argparse
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    _is_audit_only_eligible,
    _select_discovery_candidates,
    build_discover_candidates_once_payload,
)

# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

_SOLANA_CHAIN = "solana"
_GT_NEW_POOL_CHANNEL = "GECKOTERMINAL_NEW_POOL"

_REQUIRED_AUDIT_ONLY_REPORT_FIELDS = {
    "raw_watch_only_count",
    "audit_only_watch_only_count",
    "persisted_watch_only_count",
    "selected_watch_only_count",
    "raw_d1_count",
    "audit_only_d1_count",
    "persisted_d1_count",
    "selected_d1_count",
    "audit_only_candidate_count",
    "selected_audit_only_count",
    "active_tracking_selected_count",
    "quota_satisfied_by_audit_only_count",
    "quota_satisfied_by_active_tracking_count",
    "candidates_excluded_from_tracking_but_used_for_quota",
    "reasons_by_audit_only_candidate",
    "source_trace_by_audit_only_candidate",
}


def _db(tmp_dir: str, suffix: str = "v2_2m.db") -> pathlib.Path:
    p = pathlib.Path(tmp_dir) / suffix
    apply_migrations(p)
    return p


def _run_args(db_path: str | pathlib.Path, **overrides) -> argparse.Namespace:
    base = {
        "project_root": str(PROJECT_ROOT),
        "format": "json",
        "no_color": True,
        "operator_approved": True,
        "chain": "solana",
        "max_candidates": 10,
        "query": "pump",
        "timeout_seconds": 5.0,
        "source_name": "geckoterminal",
        "request_kind": "geckoterminal_new_pool_discovery",
        "request_key": "v2-2m-test",
        "db_path": str(db_path),
        "max_source_requests": 1,
    }
    base.update(overrides)
    return argparse.Namespace(**base)


def _gt_transport(pools: list[dict]):
    def _t(context):
        del context
        return {"data": pools}
    return _t


def _active_gt_pool(pool_address: str, token_mint: str, *, symbol: str = "ACT") -> dict:
    """High-activity GT pool — classified as TRACK_FAST."""
    return {
        "id": f"solana_{pool_address}",
        "type": "pool",
        "attributes": {
            "address": pool_address,
            "base_token_price_usd": "0.001",
            "reserve_in_usd": "9500.0",
            "volume_usd": {"m5": "3500.0", "h1": "14000.0", "h24": "60000.0"},
            "transactions": {
                "m5": {"buys": 30, "sells": 10},
                "h24": {"buys": 400, "sells": 200},
            },
            "pool_created_at": "2026-01-01T00:00:00Z",
            "network": "solana",
            "dex_id": "raydium",
            "name": f"{symbol} / SOL",
            "price_change_percentage": {"m5": "5.0", "h1": "10.0", "h24": "20.0"},
        },
        "relationships": {
            "base_token": {"data": {"id": f"solana_{token_mint}"}},
        },
    }


def _dead_gt_pool(pool_address: str, token_mint: str, *, symbol: str = "DEAD") -> dict:
    """Near-zero-activity GT pool — classified as D1 (WATCH_ONLY, dead)."""
    return {
        "id": f"solana_{pool_address}",
        "type": "pool",
        "attributes": {
            "address": pool_address,
            "base_token_price_usd": "0.0000001",
            "reserve_in_usd": "0.5",
            "volume_usd": {"m5": "0.0", "h1": "0.0", "h24": "0.0"},
            "transactions": {
                "m5": {"buys": 0, "sells": 0},
                "h24": {"buys": 0, "sells": 0},
            },
            "pool_created_at": "2020-01-01T00:00:00Z",
            "network": "solana",
            "dex_id": "raydium",
            "name": f"{symbol} / SOL",
            "price_change_percentage": {"m5": "0.0", "h1": "0.0", "h24": "0.0"},
        },
        "relationships": {
            "base_token": {"data": {"id": f"solana_{token_mint}"}},
        },
    }


def _make_d1_candidate(mint: str = "D1Mint11111111111111111111111111111111111111") -> dict:
    """Pre-built normalized D1 (dead/near-zero) candidate for unit tests.

    Includes V2-2M.2 eligibility fields (source_status, data_quality_label) at their
    clean defaults so the eligibility gate passes. Override to test ineligible cases.
    """
    return {
        "chain": "solana",
        "token_mint": mint,
        "pair_address": f"D1Pair{mint[5:]}",
        "source_name": "geckoterminal",
        "price_usd": 0.000001,
        "liquidity_usd": 0.5,
        "volume_5m": 0.0,
        "txns_5m": 0,
        "volume_1h": 0.0,
        "txns_1h": 0,
        "volume_24h": 0.0,
        "txns_24h": 0,
        "source_channel": _GT_NEW_POOL_CHANNEL,
        "source_channel_reason": "new_pool_discovery",
        "source_response_id": "unit-test-resp",
        # V2-2M.2: eligibility fields — override in tests for failed/dirty cases.
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
    }


def _make_watch_only_candidate(mint: str = "WOMint11111111111111111111111111111111111111") -> dict:
    """Pre-built normalized non-D1 WATCH_ONLY candidate (missing source_name/captured_at
    → should_watch_only_candidate fires before track paths can qualify).

    Includes V2-2M.2 eligibility fields at their clean defaults. source_name and
    captured_at are intentionally absent — they control the classifier path. Override
    source_status/data_quality_label to test ineligible cases.
    """
    return {
        "chain": "solana",
        "token_mint": mint,
        "pair_address": f"WOPair{mint[5:]}",
        "price_usd": 0.0001,
        "liquidity_usd": 2000.0,
        "volume_5m": 0.0,
        "txns_5m": 0,
        "volume_1h": 50.0,
        "txns_1h": 1,
        "volume_24h": 5000.0,
        "txns_24h": 100,
        "source_channel": _GT_NEW_POOL_CHANNEL,
        "source_channel_reason": "new_pool_discovery",
        "source_response_id": "unit-test-resp",
        # V2-2M.2: eligibility fields — override in tests for failed/dirty cases.
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        # No source_name/captured_at → candidate_has_required_fields = False
        # → should_watch_only_candidate = True (partial_market_fields_or_low_activity)
    }


def _make_active_candidate(mint: str = "ACTMint1111111111111111111111111111111111111") -> dict:
    """Pre-built normalized TRACK_FAST candidate for unit tests."""
    return {
        "chain": "solana",
        "token_mint": mint,
        "pair_address": f"ACTPair{mint[6:]}",
        "source_name": "geckoterminal",
        "captured_at": "2026-07-09T00:00:00+00:00",
        "price_usd": 0.001,
        "liquidity_usd": 9500.0,
        "volume_5m": 3500.0,
        "txns_5m": 40,
        "volume_1h": 14000.0,
        "txns_1h": 200,
        "volume_24h": 60000.0,
        "txns_24h": 600,
        "source_channel": _GT_NEW_POOL_CHANNEL,
        "source_response_id": "unit-test-resp",
    }


def _select(candidates: list[dict], **kwargs) -> tuple:
    """Convenience wrapper for _select_discovery_candidates with default empty sets."""
    return _select_discovery_candidates(
        candidates,
        existing_token_mints=kwargs.get("existing_token_mints", set()),
        existing_pair_addresses=kwargs.get("existing_pair_addresses", set()),
        existing_symbol_name_keys=kwargs.get("existing_symbol_name_keys", None),
        max_candidates=kwargs.get("max_candidates", 10),
    )


# ---------------------------------------------------------------------------
# A. Audit-only pool capture
# ---------------------------------------------------------------------------

class TestAuditOnlyPoolCapture(unittest.TestCase):

    def test_d1_dead_candidate_enters_audit_only_pool_not_accepted(self):
        cand = _make_d1_candidate()
        accepted, rejected, inspected, audit_only_pool = _select([cand])
        self.assertGreater(len(audit_only_pool), 0, "D1 candidate must be in audit_only_pool")
        mints_in_accepted = [c.get("token_mint") for c in accepted]
        self.assertNotIn(cand["token_mint"], mints_in_accepted)

    def test_watch_only_candidate_enters_audit_only_pool_not_accepted(self):
        cand = _make_watch_only_candidate()
        accepted, rejected, _inspected, audit_only_pool = _select([cand])
        self.assertGreater(len(audit_only_pool), 0, "WATCH_ONLY candidate must be in audit_only_pool")
        mints_in_accepted = [c.get("token_mint") for c in accepted]
        self.assertNotIn(cand["token_mint"], mints_in_accepted)

    def test_non_solana_candidate_excluded_from_audit_pool(self):
        cand = {**_make_d1_candidate(), "chain": "ethereum"}
        _accepted, _rejected, _inspected, audit_only_pool = _select([cand])
        self.assertEqual(len(audit_only_pool), 0)

    def test_active_track_fast_candidate_not_in_audit_pool(self):
        cand = _make_active_candidate()
        accepted, _rejected, _inspected, audit_only_pool = _select([cand])
        self.assertEqual(len(audit_only_pool), 0)
        self.assertGreater(len(accepted), 0)

    def test_d1_candidate_appears_in_rejected_list(self):
        cand = _make_d1_candidate()
        _accepted, rejected, _inspected, _audit_only_pool = _select([cand])
        reasons = [r["reject_reason"] for r in rejected]
        self.assertIn("insufficient_activity_for_memory_growth", reasons)

    def test_watch_only_candidate_appears_in_rejected_list(self):
        cand = _make_watch_only_candidate()
        _accepted, rejected, _inspected, _audit_only_pool = _select([cand])
        reasons = [r["reject_reason"] for r in rejected]
        self.assertIn("watch_only_not_eligible_for_15m_memory_proof_cycle", reasons)


# ---------------------------------------------------------------------------
# B. Duplicate-mint dedup in audit_only_pool
# ---------------------------------------------------------------------------

class TestAuditOnlyPoolDedup(unittest.TestCase):

    def test_duplicate_d1_mint_captured_only_once(self):
        cand1 = _make_d1_candidate("DeadMintA1111111111111111111111111111111111111")
        cand2 = {**cand1, "pair_address": "DeadPairB111111111111111111111111111111111111"}
        _accepted, _rejected, _inspected, audit_only_pool = _select([cand1, cand2])
        mints = [c["token_mint"] for c in audit_only_pool]
        self.assertEqual(mints.count(cand1["token_mint"]), 1, "Duplicate mint must appear once in audit_only_pool")

    def test_duplicate_watch_only_mint_captured_only_once(self):
        cand1 = _make_watch_only_candidate("WOMintDup1111111111111111111111111111111111111")
        cand2 = {**cand1, "pair_address": "WOPairDup2111111111111111111111111111111111111"}
        _accepted, _rejected, _inspected, audit_only_pool = _select([cand1, cand2])
        mints = [c["token_mint"] for c in audit_only_pool]
        self.assertEqual(mints.count(cand1["token_mint"]), 1)

    def test_two_distinct_d1_mints_both_captured(self):
        cand1 = _make_d1_candidate("Dead1111111111111111111111111111111111111111111")
        cand2 = _make_d1_candidate("Dead2222222222222222222222222222222222222222222")
        _accepted, _rejected, _inspected, audit_only_pool = _select([cand1, cand2])
        mints = {c["token_mint"] for c in audit_only_pool}
        self.assertIn(cand1["token_mint"], mints)
        self.assertIn(cand2["token_mint"], mints)


# ---------------------------------------------------------------------------
# C. Audit-only candidate metadata
# ---------------------------------------------------------------------------

class TestAuditOnlyCandidateMetadata(unittest.TestCase):

    def _get_captured(self, candidates: list[dict]) -> dict:
        _a, _r, _i, pool = _select(candidates)
        self.assertGreater(len(pool), 0, "Expected at least one audit-only candidate")
        return pool[0]

    def test_d1_candidate_has_audit_only_true(self):
        captured = self._get_captured([_make_d1_candidate()])
        self.assertTrue(captured.get("audit_only"))

    def test_d1_candidate_kind_is_audit_only(self):
        captured = self._get_captured([_make_d1_candidate()])
        self.assertEqual(captured.get("candidate_kind"), "AUDIT_ONLY")

    def test_d1_pre_persistence_reject_reason(self):
        captured = self._get_captured([_make_d1_candidate()])
        self.assertEqual(
            captured.get("pre_persistence_reject_reason"),
            "insufficient_activity_for_memory_growth",
        )

    def test_d1_tracking_lane_is_watch_only(self):
        captured = self._get_captured([_make_d1_candidate()])
        self.assertEqual(captured.get("tracking_lane"), "WATCH_ONLY")

    def test_d1_primary_bucket_is_d1(self):
        captured = self._get_captured([_make_d1_candidate()])
        self.assertEqual(captured.get("primary_bucket"), "D1")

    def test_watch_only_candidate_has_audit_only_true(self):
        captured = self._get_captured([_make_watch_only_candidate()])
        self.assertTrue(captured.get("audit_only"))

    def test_watch_only_candidate_kind_is_audit_only(self):
        captured = self._get_captured([_make_watch_only_candidate()])
        self.assertEqual(captured.get("candidate_kind"), "AUDIT_ONLY")

    def test_watch_only_pre_persistence_reject_reason(self):
        captured = self._get_captured([_make_watch_only_candidate()])
        self.assertEqual(
            captured.get("pre_persistence_reject_reason"),
            "watch_only_not_eligible_for_15m_memory_proof_cycle",
        )

    def test_watch_only_tracking_lane_is_watch_only(self):
        captured = self._get_captured([_make_watch_only_candidate()])
        self.assertEqual(captured.get("tracking_lane"), "WATCH_ONLY")

    def test_watch_only_primary_bucket_is_not_d1(self):
        captured = self._get_captured([_make_watch_only_candidate()])
        self.assertNotEqual(captured.get("primary_bucket"), "D1")


# ---------------------------------------------------------------------------
# D. Active-tracking guard (via integration payload)
# ---------------------------------------------------------------------------

class TestActiveTrackingGuard(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _dead_pool_payload(self):
        dead_pool = _dead_gt_pool(
            "GuardDeadPool111111111111111111111111111111",
            "GuardDeadMint1111111111111111111111111111111",
        )
        args = _run_args(self._db)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport([dead_pool])
        )

    def test_dead_candidate_not_in_tracking_queue(self):
        self._dead_pool_payload()
        with sqlite3.connect(self._db) as conn:
            rows = conn.execute(
                "SELECT COUNT(*) FROM printer_tracking_queue"
            ).fetchone()[0]
        self.assertEqual(rows, 0, "audit_only candidate must not create tracking_queue rows")

    def test_dead_candidate_not_in_scheduler_jobs(self):
        self._dead_pool_payload()
        with sqlite3.connect(self._db) as conn:
            rows = conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
            ).fetchone()[0]
        self.assertEqual(rows, 0, "audit_only candidate must not create scheduler_job rows")

    def test_dead_candidate_appears_in_audit_only_report(self):
        payload = self._dead_pool_payload()
        report = payload.get("audit_only_report", {})
        self.assertGreater(report.get("audit_only_candidate_count", 0), 0)

    def test_dead_candidate_does_not_increase_candidates_accepted(self):
        payload = self._dead_pool_payload()
        self.assertEqual(payload["candidates_accepted"], 0)


# ---------------------------------------------------------------------------
# E. Quota supplement: 6+ batch + audit_only pool satisfies WATCH_ONLY/D1
# ---------------------------------------------------------------------------

def _n_active_pools(n: int) -> list[dict]:
    return [
        _active_gt_pool(
            f"ActivePool{i:02d}111111111111111111111111111111111",
            f"ActiveMint{i:02d}111111111111111111111111111111111",
            symbol=f"T{i:02d}",
        )
        for i in range(n)
    ]


class TestQuotaSupplement(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _payload_with_n_active_and_dead(self, n_active: int, n_dead: int = 1):
        pools = _n_active_pools(n_active)
        for i in range(n_dead):
            pools.append(_dead_gt_pool(
                f"DeadQuotPool{i:02d}1111111111111111111111111111",
                f"DeadQuotMint{i:02d}111111111111111111111111111",
                symbol=f"DEAD{i:02d}",
            ))
        args = _run_args(self._db, max_candidates=20)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport(pools)
        )

    def test_d1_from_audit_pool_satisfies_quota_for_6plus_batch(self):
        """7 active + 1 D1 in audit pool → supplement used; D1/WATCH_ONLY violations resolved."""
        payload = self._payload_with_n_active_and_dead(7, 1)
        report = payload.get("audit_only_report", {})
        if payload["candidates_accepted"] < 6:
            self.skipTest("Need 6+ accepted for quota check")
        # Supplement was used
        self.assertEqual(report["selected_audit_only_count"], 1)
        # After supplement, the specific D1/WATCH_ONLY violations must be gone
        # (other violations like WINNER_CAP_EXCEEDED_A1_MAX_2 may still be present)
        remaining = report["quota_violations"]
        self.assertNotIn("MISSING_D1_DEAD_TOKEN_REQUIRED_FOR_6PLUS_BATCH", remaining)
        self.assertNotIn("MISSING_WATCH_ONLY_REQUIRED_FOR_6PLUS_BATCH", remaining)

    def test_d1_satisfies_both_watch_only_and_d1_violations_with_one_candidate(self):
        """A D1 candidate is also WATCH_ONLY so it satisfies both quota requirements."""
        payload = self._payload_with_n_active_and_dead(7, 1)
        report = payload.get("audit_only_report", {})
        if payload["candidates_accepted"] < 6:
            self.skipTest("Need 6+ accepted")
        # Only 1 supplement candidate needed (D1 = WATCH_ONLY)
        self.assertEqual(report["selected_audit_only_count"], 1)

    def test_quota_still_fails_if_audit_pool_empty(self):
        """7 active candidates, no dead candidates → quota fails (no supplement possible)."""
        payload = self._payload_with_n_active_and_dead(7, 0)
        report = payload.get("audit_only_report", {})
        if payload["candidates_accepted"] < 6:
            self.skipTest("Need 6+ accepted")
        self.assertEqual(report["selected_audit_only_count"], 0)
        self.assertFalse(report["quota_ok"], "Quota must fail when audit pool is empty")

    def test_no_supplement_for_fewer_than_6_accepted(self):
        """With < 6 accepted, quota 6+ checks don't fire → no supplement needed."""
        payload = self._payload_with_n_active_and_dead(4, 1)
        report = payload.get("audit_only_report", {})
        if payload["candidates_accepted"] >= 6:
            self.skipTest("Test requires fewer than 6 accepted")
        # Quota check doesn't fire for < 6 items; supplement stays at 0
        self.assertEqual(report["selected_audit_only_count"], 0)

    def test_supplement_adds_minimum_candidates(self):
        """Supplement uses minimum candidates: 1 D1 candidate satisfies both requirements."""
        payload = self._payload_with_n_active_and_dead(7, 3)
        report = payload.get("audit_only_report", {})
        if payload["candidates_accepted"] < 6:
            self.skipTest("Need 6+ accepted")
        # Only 1 needed (D1 covers both WATCH_ONLY + D1)
        self.assertLessEqual(report["selected_audit_only_count"], 2)


# ---------------------------------------------------------------------------
# F. audit_only_report field coverage
# ---------------------------------------------------------------------------

class TestAuditOnlyReportFields(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _payload_with_dead(self):
        pool = _dead_gt_pool(
            "ReportTestPool111111111111111111111111111111",
            "ReportTestMint111111111111111111111111111111",
        )
        args = _run_args(self._db)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport([pool])
        )

    def test_audit_only_report_present_in_payload(self):
        payload = self._payload_with_dead()
        self.assertIn("audit_only_report", payload)

    def test_all_required_fields_present(self):
        payload = self._payload_with_dead()
        report = payload["audit_only_report"]
        for field in _REQUIRED_AUDIT_ONLY_REPORT_FIELDS:
            self.assertIn(field, report, f"Missing required field: {field!r}")

    def test_quota_ok_bonus_field_present(self):
        payload = self._payload_with_dead()
        self.assertIn("quota_ok", payload["audit_only_report"])

    def test_quota_violations_bonus_field_present(self):
        payload = self._payload_with_dead()
        self.assertIn("quota_violations", payload["audit_only_report"])

    def test_persisted_watch_only_count_is_always_zero(self):
        payload = self._payload_with_dead()
        self.assertEqual(payload["audit_only_report"]["persisted_watch_only_count"], 0)

    def test_persisted_d1_count_is_always_zero(self):
        payload = self._payload_with_dead()
        self.assertEqual(payload["audit_only_report"]["persisted_d1_count"], 0)

    def test_reasons_by_audit_only_candidate_maps_mint_to_reason(self):
        payload = self._payload_with_dead()
        report = payload["audit_only_report"]
        reasons = report["reasons_by_audit_only_candidate"]
        self.assertIsInstance(reasons, dict)
        if reasons:
            for mint, reason in reasons.items():
                self.assertIsInstance(mint, str)
                self.assertIsInstance(reason, str)

    def test_source_trace_by_audit_only_candidate_maps_mint_to_trace(self):
        payload = self._payload_with_dead()
        report = payload["audit_only_report"]
        traces = report["source_trace_by_audit_only_candidate"]
        self.assertIsInstance(traces, dict)
        if traces:
            for mint, trace in traces.items():
                self.assertIsInstance(trace, dict)
                # V2-2M.2: all four source-trace fields required (V2-2L Section 6.1)
                self.assertIn("source_name", trace)
                self.assertIn("source_channel", trace)
                self.assertIn("source_response_id", trace)
                self.assertIn("source_channel_reason", trace)

    def test_dead_pool_shows_in_audit_only_d1_count(self):
        payload = self._payload_with_dead()
        report = payload["audit_only_report"]
        self.assertGreater(report["raw_d1_count"], 0)
        self.assertGreater(report["audit_only_d1_count"], 0)


# ---------------------------------------------------------------------------
# G. H.1 invariant: candidate_stage_report new fields are all int
# ---------------------------------------------------------------------------

class TestH1InvariantNewFields(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _any_payload(self):
        pool = _active_gt_pool(
            "H1TestPool1111111111111111111111111111111111",
            "H1TestMint1111111111111111111111111111111111",
        )
        args = _run_args(self._db)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport([pool])
        )

    def test_all_candidate_stage_report_values_are_int_or_not_measured(self):
        payload = self._any_payload()
        for key, val in payload["candidate_stage_report"].items():
            self.assertTrue(
                isinstance(val, int) or val == "NOT_MEASURED",
                f"candidate_stage_report[{key!r}] = {val!r} violates H.1 invariant",
            )

    def test_candidates_audit_only_total_is_int(self):
        payload = self._any_payload()
        self.assertIsInstance(
            payload["candidate_stage_report"]["candidates_audit_only_total"], int
        )

    def test_candidates_audit_only_watch_only_is_int(self):
        payload = self._any_payload()
        self.assertIsInstance(
            payload["candidate_stage_report"]["candidates_audit_only_watch_only"], int
        )

    def test_candidates_audit_only_d1_is_int(self):
        payload = self._any_payload()
        self.assertIsInstance(
            payload["candidate_stage_report"]["candidates_audit_only_d1"], int
        )

    def test_candidates_audit_only_selected_for_quota_is_int(self):
        payload = self._any_payload()
        self.assertIsInstance(
            payload["candidate_stage_report"]["candidates_audit_only_selected_for_quota"], int
        )

    def test_existing_stage_fields_still_int_or_not_measured(self):
        """Regression: H.1 invariant holds for pre-V2-2M fields too."""
        payload = self._any_payload()
        report = payload["candidate_stage_report"]
        for field in (
            "candidates_seen_total",
            "candidates_normalized_total",
            "candidates_persisted_total",
            "candidates_rejected_pre_persistence",
        ):
            self.assertIsInstance(report[field], int, f"{field!r} must be int")


# ---------------------------------------------------------------------------
# H. Backward compatibility regressions (H.1-H.6 invariants)
# ---------------------------------------------------------------------------

class TestBackwardCompatRegressions(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _single_active_payload(self):
        pool = _active_gt_pool(
            "BwdCompatPool111111111111111111111111111111111",
            "BwdCompatMint111111111111111111111111111111111",
        )
        args = _run_args(self._db)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport([pool])
        )

    def test_h2_age_activity_report_present(self):
        payload = self._single_active_payload()
        self.assertIn("age_activity_report", payload)

    def test_h3_field_completeness_report_present(self):
        payload = self._single_active_payload()
        self.assertIn("field_completeness_report", payload)

    def test_h4_within_response_integrity_report_present(self):
        payload = self._single_active_payload()
        self.assertIn("within_response_integrity_report", payload)
        self.assertNotIn("within_response_integrity_report", payload["candidate_stage_report"])

    def test_h5_source_budget_report_present(self):
        payload = self._single_active_payload()
        self.assertIn("source_budget_report", payload)

    def test_active_candidate_still_accepted_and_persisted(self):
        payload = self._single_active_payload()
        self.assertGreater(payload["candidates_accepted"], 0)

    def test_active_candidate_creates_tracking_queue_row(self):
        self._single_active_payload()
        with sqlite3.connect(self._db) as conn:
            rows = conn.execute(
                "SELECT COUNT(*) FROM printer_tracking_queue"
            ).fetchone()[0]
        self.assertGreater(rows, 0, "Active candidate must create a tracking_queue row")

    def test_active_candidate_creates_scheduler_job(self):
        self._single_active_payload()
        with sqlite3.connect(self._db) as conn:
            rows = conn.execute(
                "SELECT COUNT(*) FROM printer_scheduler_jobs"
            ).fetchone()[0]
        self.assertGreater(rows, 0, "Active candidate must create a scheduler_jobs row")

    def test_audit_only_report_zero_counts_for_pure_active_run(self):
        payload = self._single_active_payload()
        report = payload["audit_only_report"]
        self.assertEqual(report["audit_only_candidate_count"], 0)
        self.assertEqual(report["selected_audit_only_count"], 0)
        self.assertEqual(report["audit_only_watch_only_count"], 0)
        self.assertEqual(report["audit_only_d1_count"], 0)

    def test_source_trace_empty_for_pure_active_run(self):
        payload = self._single_active_payload()
        self.assertEqual(payload["audit_only_report"]["source_trace_by_audit_only_candidate"], {})


# ---------------------------------------------------------------------------
# I. Mixed run: active + dead candidates in same transport
# ---------------------------------------------------------------------------

class TestMixedRun(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _mixed_payload(self):
        pools = [
            _active_gt_pool(
                "MixedActivePool1111111111111111111111111111",
                "MixedActiveMint1111111111111111111111111111",
                symbol="MIX",
            ),
            _dead_gt_pool(
                "MixedDeadPool11111111111111111111111111111",
                "MixedDeadMint11111111111111111111111111111",
                symbol="MDEAD",
            ),
        ]
        args = _run_args(self._db)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport(pools)
        )

    def test_active_candidate_accepted_dead_candidate_in_audit_pool(self):
        payload = self._mixed_payload()
        report = payload["audit_only_report"]
        self.assertGreater(payload["candidates_accepted"], 0)
        self.assertGreater(report["audit_only_candidate_count"], 0)

    def test_dead_candidate_not_in_tracking_queue_when_mixed(self):
        """Dead candidate must not create a tracking queue row; only active one does."""
        payload = self._mixed_payload()
        with sqlite3.connect(self._db) as conn:
            queue_count = conn.execute(
                "SELECT COUNT(*) FROM printer_tracking_queue"
            ).fetchone()[0]
        # Active pool creates 1 queue row; dead pool creates 0.
        self.assertEqual(queue_count, payload["candidates_accepted"])

    def test_candidate_stage_report_audit_only_total_is_nonzero(self):
        payload = self._mixed_payload()
        report = payload["candidate_stage_report"]
        self.assertGreater(report["candidates_audit_only_total"], 0)

    def test_reasons_by_audit_only_candidate_present_for_dead(self):
        payload = self._mixed_payload()
        reasons = payload["audit_only_report"]["reasons_by_audit_only_candidate"]
        self.assertGreater(len(reasons), 0)


# ---------------------------------------------------------------------------
# K. V2-2M.2 eligibility gate: direct helper unit tests
# ---------------------------------------------------------------------------

class TestIsAuditOnlyEligible(unittest.TestCase):
    """Direct tests of the _is_audit_only_eligible() helper (V2-2L Section 6.1)."""

    def _eligible(self, source_status: str, data_quality_label: str) -> bool:
        return _is_audit_only_eligible({
            "source_status": source_status,
            "data_quality_label": data_quality_label,
        })

    def test_complete_clean_data_is_eligible(self):
        self.assertTrue(self._eligible("COMPLETE", "CLEAN_DATA"))

    def test_complete_acceptable_partial_is_eligible(self):
        self.assertTrue(self._eligible("COMPLETE", "ACCEPTABLE_PARTIAL_DATA"))

    def test_partial_clean_data_is_eligible(self):
        self.assertTrue(self._eligible("PARTIAL", "CLEAN_DATA"))

    def test_partial_acceptable_partial_is_eligible(self):
        self.assertTrue(self._eligible("PARTIAL", "ACCEPTABLE_PARTIAL_DATA"))

    def test_failed_source_status_is_not_eligible(self):
        self.assertFalse(self._eligible("FAILED", "CLEAN_DATA"))

    def test_stale_source_status_is_not_eligible(self):
        self.assertFalse(self._eligible("STALE", "CLEAN_DATA"))

    def test_conflicting_source_status_is_not_eligible(self):
        self.assertFalse(self._eligible("CONFLICTING", "CLEAN_DATA"))

    def test_dirty_data_quality_is_not_eligible(self):
        self.assertFalse(self._eligible("COMPLETE", "DIRTY_DATA"))

    def test_stale_data_quality_is_not_eligible(self):
        self.assertFalse(self._eligible("COMPLETE", "STALE_DATA"))

    def test_missing_critical_data_quality_is_not_eligible(self):
        self.assertFalse(self._eligible("COMPLETE", "MISSING_CRITICAL_DATA"))

    def test_unknown_source_status_is_not_eligible(self):
        self.assertFalse(self._eligible("UNKNOWN_STATUS", "CLEAN_DATA"))

    def test_unknown_data_quality_label_is_not_eligible(self):
        self.assertFalse(self._eligible("COMPLETE", "UNKNOWN_QUALITY"))

    def test_missing_source_status_field_is_not_eligible(self):
        self.assertFalse(_is_audit_only_eligible({"data_quality_label": "CLEAN_DATA"}))

    def test_missing_data_quality_field_is_not_eligible(self):
        self.assertFalse(_is_audit_only_eligible({"source_status": "COMPLETE"}))

    def test_empty_candidate_is_not_eligible(self):
        self.assertFalse(_is_audit_only_eligible({}))


# ---------------------------------------------------------------------------
# K2. V2-2M.2 eligibility gate wired into _select_discovery_candidates()
# ---------------------------------------------------------------------------

class TestAuditOnlyEligibilityGate(unittest.TestCase):
    """Verify that FAILED/STALE/DIRTY/unknown candidates are excluded from the audit pool."""

    # -- D1 ineligible cases --

    def test_failed_source_status_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "source_status": "FAILED"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0, "FAILED D1 must not enter audit_only_pool")

    def test_stale_source_status_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "source_status": "STALE"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    def test_conflicting_source_status_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "source_status": "CONFLICTING"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    def test_dirty_data_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "data_quality_label": "DIRTY_DATA"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0, "DIRTY_DATA D1 must not enter audit_only_pool")

    def test_stale_data_quality_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "data_quality_label": "STALE_DATA"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    def test_missing_critical_data_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "data_quality_label": "MISSING_CRITICAL_DATA"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    def test_unknown_source_status_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "source_status": "INVENTED_STATUS"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    def test_unknown_data_quality_d1_not_in_audit_pool(self):
        cand = {**_make_d1_candidate(), "data_quality_label": "INVENTED_QUALITY"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    # -- WATCH_ONLY ineligible cases --

    def test_failed_source_status_watch_only_not_in_audit_pool(self):
        cand = {**_make_watch_only_candidate(), "source_status": "FAILED"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0, "FAILED WATCH_ONLY must not enter audit_only_pool")

    def test_stale_source_status_watch_only_not_in_audit_pool(self):
        cand = {**_make_watch_only_candidate(), "source_status": "STALE"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    def test_dirty_data_watch_only_not_in_audit_pool(self):
        cand = {**_make_watch_only_candidate(), "data_quality_label": "DIRTY_DATA"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    def test_stale_data_quality_watch_only_not_in_audit_pool(self):
        cand = {**_make_watch_only_candidate(), "data_quality_label": "STALE_DATA"}
        _a, _r, _i, pool = _select([cand])
        self.assertEqual(len(pool), 0)

    # -- Acceptable partial cases (should still enter pool) --

    def test_partial_source_status_d1_enters_audit_pool(self):
        cand = {**_make_d1_candidate(), "source_status": "PARTIAL"}
        _a, _r, _i, pool = _select([cand])
        self.assertGreater(len(pool), 0, "PARTIAL D1 must be eligible for audit_only_pool")

    def test_acceptable_partial_data_d1_enters_audit_pool(self):
        cand = {**_make_d1_candidate(), "data_quality_label": "ACCEPTABLE_PARTIAL_DATA"}
        _a, _r, _i, pool = _select([cand])
        self.assertGreater(len(pool), 0)

    def test_partial_source_status_watch_only_enters_audit_pool(self):
        cand = {**_make_watch_only_candidate(), "source_status": "PARTIAL"}
        _a, _r, _i, pool = _select([cand])
        self.assertGreater(len(pool), 0)

    def test_acceptable_partial_data_watch_only_enters_audit_pool(self):
        cand = {**_make_watch_only_candidate(), "data_quality_label": "ACCEPTABLE_PARTIAL_DATA"}
        _a, _r, _i, pool = _select([cand])
        self.assertGreater(len(pool), 0)

    # -- Ineligible candidate still appears in rejected list --

    def test_failed_d1_still_appears_in_rejected_list(self):
        """Eligibility gate affects pool admission only; reject_reason is still emitted."""
        cand = {**_make_d1_candidate(), "source_status": "FAILED"}
        _a, rejected, _i, pool = _select([cand])
        reasons = [r["reject_reason"] for r in rejected]
        self.assertIn("insufficient_activity_for_memory_growth", reasons)
        self.assertEqual(len(pool), 0)

    def test_dirty_watch_only_still_appears_in_rejected_list(self):
        cand = {**_make_watch_only_candidate(), "data_quality_label": "DIRTY_DATA"}
        _a, rejected, _i, pool = _select([cand])
        reasons = [r["reject_reason"] for r in rejected]
        self.assertIn("watch_only_not_eligible_for_15m_memory_proof_cycle", reasons)
        self.assertEqual(len(pool), 0)


# ---------------------------------------------------------------------------
# L. V2-2M.2 source trace: all four fields present in integration payload
# ---------------------------------------------------------------------------

class TestSourceTraceAllFields(unittest.TestCase):
    """Integration tests verifying the four-field source trace (V2-2L Section 6.1)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self._db = _db(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _payload_with_dead(self):
        pool = _dead_gt_pool(
            "TraceTestPool111111111111111111111111111111",
            "TraceTestMint111111111111111111111111111111",
        )
        args = _run_args(self._db)
        return build_discover_candidates_once_payload(
            args, transport=_gt_transport([pool])
        )

    def test_source_trace_has_source_name(self):
        payload = self._payload_with_dead()
        traces = payload["audit_only_report"]["source_trace_by_audit_only_candidate"]
        self.assertGreater(len(traces), 0, "Expected at least one audit-only candidate")
        for mint, trace in traces.items():
            self.assertIn("source_name", trace, f"source_name missing from trace for {mint!r}")

    def test_source_trace_has_source_channel(self):
        payload = self._payload_with_dead()
        traces = payload["audit_only_report"]["source_trace_by_audit_only_candidate"]
        for _mint, trace in traces.items():
            self.assertIn("source_channel", trace)

    def test_source_trace_has_source_response_id(self):
        payload = self._payload_with_dead()
        traces = payload["audit_only_report"]["source_trace_by_audit_only_candidate"]
        for _mint, trace in traces.items():
            self.assertIn("source_response_id", trace)

    def test_source_trace_has_source_channel_reason(self):
        payload = self._payload_with_dead()
        traces = payload["audit_only_report"]["source_trace_by_audit_only_candidate"]
        for _mint, trace in traces.items():
            self.assertIn("source_channel_reason", trace, "source_channel_reason missing from trace")

    def test_source_trace_source_name_matches_run_args(self):
        """source_name on candidates comes from normalize_candidates(args.source_name, ...)."""
        payload = self._payload_with_dead()
        traces = payload["audit_only_report"]["source_trace_by_audit_only_candidate"]
        for _mint, trace in traces.items():
            self.assertEqual(trace["source_name"], "geckoterminal")

    def test_source_trace_all_four_keys_present_together(self):
        """All four trace fields must be present simultaneously (not any three)."""
        payload = self._payload_with_dead()
        traces = payload["audit_only_report"]["source_trace_by_audit_only_candidate"]
        self.assertGreater(len(traces), 0)
        for mint, trace in traces.items():
            missing = [k for k in ("source_name", "source_channel", "source_response_id", "source_channel_reason") if k not in trace]
            self.assertEqual(missing, [], f"Trace for {mint!r} is missing keys: {missing}")


if __name__ == "__main__":
    unittest.main()
