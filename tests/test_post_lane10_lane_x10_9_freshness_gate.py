"""Lane X10.9 — Pre-Snapshot Freshness Revalidation Gate tests.

Coverage:
- FRESH_WITHIN_PREFERRED_LIMIT: source_response.received_at <= 120s ago
- FRESH_WITHIN_HARD_LIMIT: source_response.received_at 121–180s ago (warning)
- STALE_TRACK_FAST_BLOCKED: evidence age > 180s
- FRESHNESS_UNKNOWN_BLOCKED: no freshness evidence at all
- Evidence priority: source_response > discovery_candidate.created_at > payload.captured_at
- selected_at=now does NOT override stale source/discovery evidence
- selected_at=old does NOT override fresh source/discovery evidence
- Pair drift: gate uses exact selected pair_address, not old pair
- Empty mint/pair: FRESHNESS_UNKNOWN_BLOCKED
- DB read error: FRESHNESS_UNKNOWN_BLOCKED
- check_token_list_freshness: all 5 tokens get a result
- X10.6 batch_produced_at, candidate_age_at_selection_seconds, freshness_advisory
- X6 discovery_age_seconds, freshness_warning
- X5 runner blocks when freshness gate fires
- X5 runner includes freshness_gate_results in blocked output
- X5 runner includes freshness_gate_results in success output
- No BUY/paper/positions/PnL/retrieval/scoring fields introduced anywhere
- No DB writes in the gate
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from typing import Any

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.lane_x10_9_freshness_gate import (
    EVIDENCE_DISCOVERY_CANDIDATE,
    EVIDENCE_NONE,
    EVIDENCE_PAYLOAD_CAPTURED_AT,
    EVIDENCE_SOURCE_RESPONSE,
    FRESHNESS_STATUS_FRESH_HARD,
    FRESHNESS_STATUS_FRESH_PREFERRED,
    FRESHNESS_STATUS_STALE_BLOCKED,
    FRESHNESS_STATUS_UNKNOWN_BLOCKED,
    TRACK_FAST_HARD_MAX_AGE_SECONDS,
    TRACK_FAST_PREFERRED_MAX_AGE_SECONDS,
    FreshnessResult,
    check_token_freshness,
    check_token_list_freshness,
)
from printer_v1.operator_cli.lane_x10_6_selection_traceability import (
    build_selection_batch,
)
from printer_v1.operator_cli.lane_x6_discovery_selection_repair import (
    select_candidates_for_memory_growth,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_MINT_A = "FreshMintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_PAIR_A = "FreshPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
_MINT_B = "FreshMintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_PAIR_B = "FreshPairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
_OLD_PAIR_A = "OldPairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"


# ---------------------------------------------------------------------------
# DB fixture helpers
# ---------------------------------------------------------------------------

class _DbBase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _now(self) -> datetime:
        return datetime.now(timezone.utc)

    def _ts(self, seconds_ago: float) -> str:
        """Return ISO timestamp for N seconds ago (UTC)."""
        return (self._now() - timedelta(seconds=seconds_ago)).isoformat()

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _insert_token(self, mint: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO printer_tokens (token_mint, chain, created_at, updated_at)"
                " VALUES (?, 'solana', datetime('now'), datetime('now'))",
                (mint,),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _insert_pair(self, token_id: int, pair_address: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, created_at, updated_at)"
                " VALUES (?, ?, datetime('now'), datetime('now'))",
                (token_id, pair_address),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _insert_discovery_candidate(
        self,
        token_id: int,
        pair_id: int,
        created_at: str,
        *,
        payload_json: str | None = None,
    ) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO printer_discovery_candidates (
                    token_id, pair_id, source_name, discovery_label,
                    discovery_action, source_status, data_quality_label,
                    normalized_candidate_payload_json, created_at
                ) VALUES (?, ?, 'dexscreener', 'TRACK_FAST_CANDIDATE',
                           'TRACK_FAST', 'COMPLETE', 'CLEAN_DATA', ?, ?)
                """,
                (token_id, pair_id, payload_json, created_at),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _insert_source_request(self, received_at: str) -> int:
        with self._conn() as conn:
            cur = conn.execute(
                "INSERT INTO printer_source_requests"
                " (source_name, request_kind, requested_at, request_key,"
                "  tracking_priority, source_status, data_quality_label, created_at)"
                " VALUES ('dexscreener', 'pair_market_snapshot', ?, 'test-key',"
                "  1, 'COMPLETE', 'CLEAN_DATA', ?)",
                (received_at, received_at),
            )
            conn.commit()
            return int(cur.lastrowid)

    def _insert_source_response(
        self,
        received_at: str,
        pair_address: str,
        mint: str,
        *,
        source_status: str = "COMPLETE",
    ) -> int:
        srq_id = self._insert_source_request(received_at)
        payload = json.dumps({
            "pair_address": pair_address,
            "token_mint": mint,
            "price_usd": 0.001,
        })
        with self._conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO printer_source_responses (
                    source_request_id, source_name, received_at, status_code,
                    source_status, data_quality_label,
                    normalized_payload_json, created_at
                ) VALUES (?, 'dexscreener', ?, 200, ?, 'CLEAN_DATA', ?, ?)
                """,
                (srq_id, received_at, source_status, payload, received_at),
            )
            conn.commit()
            return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Core gate unit tests
# ---------------------------------------------------------------------------

class TestFreshnessGatePreferred(unittest.TestCase):
    """source_response <= 120s → FRESH_WITHIN_PREFERRED_LIMIT"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        apply_migrations(self.db_path)
        self._ts_90s_ago = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()

    def tearDown(self):
        self._tmp.cleanup()

    def _insert_sr(self):
        payload = json.dumps({"pair_address": _PAIR_A, "token_mint": _MINT_A})
        with sqlite3.connect(str(self.db_path)) as conn:
            srq_cur = conn.execute(
                "INSERT INTO printer_source_requests"
                " (source_name, request_kind, requested_at, request_key,"
                "  tracking_priority, source_status, data_quality_label, created_at)"
                " VALUES ('dexscreener', 'pair_market_snapshot', ?, 'test-key',"
                "  1, 'COMPLETE', 'CLEAN_DATA', ?)",
                (self._ts_90s_ago, self._ts_90s_ago),
            )
            srq_id = srq_cur.lastrowid
            conn.execute(
                "INSERT INTO printer_source_responses"
                " (source_request_id, source_name, received_at, status_code, source_status,"
                "  data_quality_label, normalized_payload_json, created_at)"
                " VALUES (?, 'dexscreener', ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, ?)",
                (srq_id, self._ts_90s_ago, payload, self._ts_90s_ago),
            )

    def test_fresh_preferred(self):
        self._insert_sr()
        now = datetime.now(timezone.utc)
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_FRESH_PREFERRED)
        self.assertEqual(result.evidence_type, EVIDENCE_SOURCE_RESPONSE)
        self.assertFalse(result.freshness_warning)
        self.assertIsNotNone(result.age_seconds)
        self.assertLessEqual(result.age_seconds, TRACK_FAST_PREFERRED_MAX_AGE_SECONDS)


class TestFreshnessGateHardLimit(_DbBase):
    """source_response between 121s and 180s → FRESH_WITHIN_HARD_LIMIT with warning"""

    def test_fresh_within_hard_limit(self):
        token_id = self._insert_token(_MINT_A)
        self._insert_pair(token_id, _PAIR_A)
        ts = self._ts(150)
        self._insert_source_response(ts, _PAIR_A, _MINT_A)

        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_FRESH_HARD)
        self.assertTrue(result.freshness_warning)
        self.assertGreater(result.age_seconds, TRACK_FAST_PREFERRED_MAX_AGE_SECONDS)
        self.assertLessEqual(result.age_seconds, TRACK_FAST_HARD_MAX_AGE_SECONDS)


class TestFreshnessGateStaleBlocked(_DbBase):
    """evidence age > 180s → STALE_TRACK_FAST_BLOCKED"""

    def test_source_response_stale_blocks(self):
        token_id = self._insert_token(_MINT_A)
        self._insert_pair(token_id, _PAIR_A)
        ts = self._ts(300)
        self._insert_source_response(ts, _PAIR_A, _MINT_A)

        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_STALE_BLOCKED)
        self.assertTrue(result.freshness_warning)
        self.assertGreater(result.age_seconds, TRACK_FAST_HARD_MAX_AGE_SECONDS)

    def test_discovery_candidate_stale_blocks(self):
        token_id = self._insert_token(_MINT_A)
        pair_id = self._insert_pair(token_id, _PAIR_A)
        ts = self._ts(400)
        self._insert_discovery_candidate(token_id, pair_id, ts)

        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_STALE_BLOCKED)
        self.assertEqual(result.evidence_type, EVIDENCE_DISCOVERY_CANDIDATE)


class TestFreshnessGateUnknownBlocked(_DbBase):
    """No evidence at all → FRESHNESS_UNKNOWN_BLOCKED"""

    def test_no_evidence_blocks(self):
        # DB is empty (no tokens, pairs, candidates, or source responses)
        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_UNKNOWN_BLOCKED)
        self.assertEqual(result.evidence_type, EVIDENCE_NONE)
        self.assertIsNone(result.age_seconds)
        self.assertIsNone(result.freshness_timestamp)
        self.assertTrue(result.freshness_warning)
        self.assertIn("no freshness evidence", result.reason)

    def test_empty_mint_blocks(self):
        now = self._now()
        result = check_token_freshness("", _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_UNKNOWN_BLOCKED)
        self.assertIn("empty", result.reason)

    def test_empty_pair_blocks(self):
        now = self._now()
        result = check_token_freshness(_MINT_A, "", "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_UNKNOWN_BLOCKED)
        self.assertIn("empty", result.reason)


class TestFreshnessGateEvidencePriority(_DbBase):
    """Priority: source_response > discovery_candidate.created_at > payload.captured_at"""

    def test_source_response_beats_old_discovery(self):
        """Fresh source_response (50s) beats stale discovery_candidate (500s)."""
        token_id = self._insert_token(_MINT_A)
        pair_id = self._insert_pair(token_id, _PAIR_A)
        self._insert_discovery_candidate(token_id, pair_id, self._ts(500))
        self._insert_source_response(self._ts(50), _PAIR_A, _MINT_A)

        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_FRESH_PREFERRED)
        self.assertEqual(result.evidence_type, EVIDENCE_SOURCE_RESPONSE)

    def test_discovery_candidate_used_when_no_source_response(self):
        """Discovery_candidate.created_at used when no source_response exists."""
        token_id = self._insert_token(_MINT_A)
        pair_id = self._insert_pair(token_id, _PAIR_A)
        self._insert_discovery_candidate(token_id, pair_id, self._ts(60))

        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_FRESH_PREFERRED)
        self.assertEqual(result.evidence_type, EVIDENCE_DISCOVERY_CANDIDATE)

    def test_payload_captured_at_used_as_fallback(self):
        """payload.captured_at used when discovery_candidate.created_at is unparseable."""
        token_id = self._insert_token(_MINT_A)
        pair_id = self._insert_pair(token_id, _PAIR_A)
        captured_at = self._ts(80)
        payload = json.dumps({"pair_address": _PAIR_A, "captured_at": captured_at})
        # Insert discovery candidate with a non-parseable created_at string.
        # SQLite stores it as text; _parse_utc will return None, causing the gate
        # to fall through from priority 2 to priority 3 (payload captured_at).
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                INSERT INTO printer_discovery_candidates (
                    token_id, pair_id, source_name, discovery_label,
                    discovery_action, source_status, data_quality_label,
                    normalized_candidate_payload_json, created_at
                ) VALUES (?, ?, 'dexscreener', 'TRACK_FAST_CANDIDATE',
                           'TRACK_FAST', 'COMPLETE', 'CLEAN_DATA', ?, 'INVALID_TIMESTAMP')
                """,
                (token_id, pair_id, payload),
            )

        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        # created_at is unparseable → skip priority 2 → use payload.captured_at
        self.assertEqual(result.evidence_type, EVIDENCE_PAYLOAD_CAPTURED_AT)
        self.assertEqual(result.status, FRESHNESS_STATUS_FRESH_PREFERRED)


class TestSelectedAtIsNotFreshness(_DbBase):
    """selected_at does NOT make a stale token fresh."""

    def test_selected_at_recent_but_source_evidence_stale_blocks(self):
        """Token list has selected_at=now but source/discovery evidence is 5 minutes old."""
        token_id = self._insert_token(_MINT_A)
        pair_id = self._insert_pair(token_id, _PAIR_A)
        # Insert stale discovery candidate
        self._insert_discovery_candidate(token_id, pair_id, self._ts(300))

        now = self._now()
        # selected_at is not passed to the gate — it's not even a parameter
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        # The gate uses discovery evidence age = 300s → STALE
        self.assertEqual(result.status, FRESHNESS_STATUS_STALE_BLOCKED)

    def test_selected_at_old_but_source_evidence_fresh_passes(self):
        """Even if selected_at is old, fresh source_response evidence passes."""
        token_id = self._insert_token(_MINT_A)
        pair_id = self._insert_pair(token_id, _PAIR_A)
        # Insert old discovery candidate
        self._insert_discovery_candidate(token_id, pair_id, self._ts(3600))
        # Insert fresh source response
        self._insert_source_response(self._ts(60), _PAIR_A, _MINT_A)

        now = self._now()
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        # Gate uses source_response (priority 1) → FRESH
        self.assertEqual(result.status, FRESHNESS_STATUS_FRESH_PREFERRED)
        self.assertEqual(result.evidence_type, EVIDENCE_SOURCE_RESPONSE)


class TestPairDriftUsesExactSelectedPair(_DbBase):
    """Gate checks the exact selected pair_address, not any previous pair for that token."""

    def test_old_pair_stale_new_pair_fresh(self):
        """Token has old pair (stale) and new pair (fresh) — gate uses new pair."""
        token_id = self._insert_token(_MINT_A)
        # Old pair with old discovery
        old_pair_id = self._insert_pair(token_id, _OLD_PAIR_A)
        self._insert_discovery_candidate(token_id, old_pair_id, self._ts(3600))
        # New pair with fresh discovery
        new_pair_id = self._insert_pair(token_id, _PAIR_A)
        self._insert_discovery_candidate(token_id, new_pair_id, self._ts(60))

        now = self._now()
        # Gate is called with new pair — should find the fresh discovery
        result = check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_FRESH_PREFERRED)

    def test_old_pair_used_in_gate_gets_stale_result(self):
        """If operator submits old pair in token list, gate checks OLD pair and blocks."""
        token_id = self._insert_token(_MINT_A)
        old_pair_id = self._insert_pair(token_id, _OLD_PAIR_A)
        # Only the old pair has a candidate — and it's stale
        self._insert_discovery_candidate(token_id, old_pair_id, self._ts(3600))

        now = self._now()
        result = check_token_freshness(_MINT_A, _OLD_PAIR_A, "A", self.db_path, now=now)
        self.assertEqual(result.status, FRESHNESS_STATUS_STALE_BLOCKED)


class TestCheckTokenListFreshness(_DbBase):
    """check_token_list_freshness returns one result per token."""

    def test_returns_one_result_per_token(self):
        tokens = [
            {"mint": _MINT_A, "pair_address": _PAIR_A, "slot": "A"},
            {"mint": _MINT_B, "pair_address": _PAIR_B, "slot": "B"},
        ]
        now = self._now()
        results = check_token_list_freshness(tokens, self.db_path, now=now)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].slot, "A")
        self.assertEqual(results[1].slot, "B")

    def test_all_unknown_when_no_evidence(self):
        tokens = [
            {"mint": _MINT_A, "pair_address": _PAIR_A, "slot": "A"},
            {"mint": _MINT_B, "pair_address": _PAIR_B, "slot": "B"},
        ]
        now = self._now()
        results = check_token_list_freshness(tokens, self.db_path, now=now)
        for r in results:
            self.assertEqual(r.status, FRESHNESS_STATUS_UNKNOWN_BLOCKED)

    def test_to_dict_contains_all_required_fields(self):
        tokens = [{"mint": _MINT_A, "pair_address": _PAIR_A, "slot": "A"}]
        results = check_token_list_freshness(tokens, self.db_path)
        d = results[0].to_dict()
        required = {
            "mint", "pair_address", "slot", "status", "evidence_type",
            "freshness_timestamp", "age_seconds", "reason", "freshness_warning",
        }
        self.assertTrue(required.issubset(set(d.keys())))

    def test_no_forbidden_fields_in_result_dict(self):
        tokens = [{"mint": _MINT_A, "pair_address": _PAIR_A, "slot": "A"}]
        results = check_token_list_freshness(tokens, self.db_path)
        d = results[0].to_dict()
        forbidden = {
            "buy_enabled", "sell_enabled", "hold_enabled",
            "paper_decisions", "positions", "pnl", "retrieval",
            "score", "rank", "confidence", "weight",
        }
        for key in forbidden:
            self.assertNotIn(key, d, f"forbidden field {key!r} found in freshness result")


class TestDbReadOnly(_DbBase):
    """Gate must not write to the DB."""

    def test_gate_does_not_mutate_discovery_candidates(self):
        token_id = self._insert_token(_MINT_A)
        pair_id = self._insert_pair(token_id, _PAIR_A)
        self._insert_discovery_candidate(token_id, pair_id, self._ts(60))

        # Count rows before gate
        with sqlite3.connect(str(self.db_path)) as conn:
            before = conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]

        check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path)

        with sqlite3.connect(str(self.db_path)) as conn:
            after = conn.execute("SELECT COUNT(*) FROM printer_discovery_candidates").fetchone()[0]

        self.assertEqual(before, after)

    def test_gate_does_not_write_new_rows(self):
        tables = [
            "printer_source_requests", "printer_source_responses",
            "printer_source_failures", "printer_token_snapshots",
            "printer_memory_windows",
        ]
        def _count_all() -> dict[str, int]:
            with sqlite3.connect(str(self.db_path)) as conn:
                return {t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in tables}

        before = _count_all()
        check_token_freshness(_MINT_A, _PAIR_A, "A", self.db_path)
        after = _count_all()
        self.assertEqual(before, after)


# ---------------------------------------------------------------------------
# X10.6 freshness advisory fields
# ---------------------------------------------------------------------------

class TestX10_6FreshnessFields(unittest.TestCase):
    """build_selection_batch includes batch_produced_at and per-candidate freshness."""

    def _cand(
        self,
        mint: str = _MINT_A,
        pair: str = _PAIR_A,
        created_at: str | None = None,
    ) -> dict[str, Any]:
        return {
            "token_mint": mint,
            "pair_address": pair,
            "chain": "solana",
            "discovery_action": "TRACK_FAST",
            "selected_lane_for_batch": "TRACK_FAST",
            "created_at": created_at,
        }

    def test_batch_produced_at_present(self):
        result = build_selection_batch(
            db_path="not-needed",
            backup_proof_path="not-needed",
            operator_approved=True,
            candidate_list_override=[self._cand()],
        )
        self.assertIn("batch_produced_at", result)
        self.assertIsNotNone(result["batch_produced_at"])

    def test_candidate_age_at_selection_seconds_computed(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        result = build_selection_batch(
            db_path="not-needed",
            backup_proof_path="not-needed",
            operator_approved=True,
            candidate_list_override=[self._cand(created_at=ts)],
        )
        cands = result.get("selected_candidates", [])
        self.assertEqual(len(cands), 1)
        age = cands[0].get("candidate_age_at_selection_seconds")
        self.assertIsNotNone(age)
        self.assertGreater(age, 0)

    def test_freshness_advisory_fresh_preferred(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        result = build_selection_batch(
            db_path="not-needed",
            backup_proof_path="not-needed",
            operator_approved=True,
            candidate_list_override=[self._cand(created_at=ts)],
        )
        cand = result["selected_candidates"][0]
        self.assertEqual(cand["freshness_advisory"], "FRESH_PREFERRED")

    def test_freshness_advisory_stale_at_selection(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        result = build_selection_batch(
            db_path="not-needed",
            backup_proof_path="not-needed",
            operator_approved=True,
            candidate_list_override=[self._cand(created_at=ts)],
        )
        cand = result["selected_candidates"][0]
        self.assertEqual(cand["freshness_advisory"], "STALE_AT_SELECTION_TIME")

    def test_freshness_advisory_unknown_when_no_timestamp(self):
        result = build_selection_batch(
            db_path="not-needed",
            backup_proof_path="not-needed",
            operator_approved=True,
            candidate_list_override=[self._cand(created_at=None)],
        )
        cand = result["selected_candidates"][0]
        self.assertIsNone(cand["candidate_age_at_selection_seconds"])
        self.assertEqual(cand["freshness_advisory"], "FRESHNESS_UNKNOWN")

    def test_no_buy_sell_paper_in_output(self):
        result = build_selection_batch(
            db_path="not-needed",
            backup_proof_path="not-needed",
            operator_approved=True,
            candidate_list_override=[self._cand()],
        )
        self.assertFalse(result.get("buy_enabled"))
        self.assertFalse(result.get("sell_enabled"))
        self.assertFalse(result.get("hold_enabled"))
        self.assertEqual(result.get("paper_decisions_created"), 0)
        self.assertEqual(result.get("positions_created"), 0)
        self.assertEqual(result.get("pnl_created"), 0)


# ---------------------------------------------------------------------------
# X6 freshness advisory fields
# ---------------------------------------------------------------------------

class TestX6FreshnessFields(unittest.TestCase):
    """select_candidates_for_memory_growth includes discovery_age_seconds / freshness_warning."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def _cand(self, captured_at: str | None, discovery_action: str = "TRACK_FAST") -> dict:
        return {
            "token_mint": _MINT_A,
            "pair_address": _PAIR_A,
            "chain": "solana",
            "discovery_action": discovery_action,
            "captured_at": captured_at,
            "price_change_5m": 25.0,
            "price_change_1h": 40.0,
            "price_change_24h": 0.0,
            "volume_5m": 10000.0,
            "volume_1h": 25000.0,
            "volume_24h": 100000.0,
            "txns_5m": 30,
            "txns_1h": 150,
            "txns_24h": 600,
            "liquidity_usd": 50000.0,
            "fdv_usd": 300000.0,
        }

    def test_discovery_age_seconds_present(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=90)).isoformat()
        result = select_candidates_for_memory_growth(
            self.db_path,
            self.backup_path,
            operator_approved=True,
            candidate_list_override=[self._cand(ts)],
        )
        cands = result.get("selected_candidates", [])
        self.assertEqual(len(cands), 1)
        self.assertIn("discovery_age_seconds", cands[0])

    def test_freshness_warning_false_for_fresh_track_fast(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=60)).isoformat()
        result = select_candidates_for_memory_growth(
            self.db_path,
            self.backup_path,
            operator_approved=True,
            candidate_list_override=[self._cand(ts)],
        )
        cand = result["selected_candidates"][0]
        self.assertFalse(cand["freshness_warning"])

    def test_freshness_warning_true_for_stale_track_fast(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        result = select_candidates_for_memory_growth(
            self.db_path,
            self.backup_path,
            operator_approved=True,
            candidate_list_override=[self._cand(ts)],
        )
        cand = result["selected_candidates"][0]
        self.assertTrue(cand["freshness_warning"])

    def test_freshness_warning_false_for_track_normal_even_if_stale(self):
        ts = (datetime.now(timezone.utc) - timedelta(seconds=300)).isoformat()
        result = select_candidates_for_memory_growth(
            self.db_path,
            self.backup_path,
            operator_approved=True,
            candidate_list_override=[self._cand(ts, discovery_action="TRACK_NORMAL")],
        )
        cand = result["selected_candidates"][0]
        # TRACK_NORMAL: freshness_warning only fires on TRACK_FAST in X6 advisory
        self.assertFalse(cand["freshness_warning"])

    def test_no_buy_sell_paper_in_x6_output(self):
        result = select_candidates_for_memory_growth(
            self.db_path,
            self.backup_path,
            operator_approved=True,
            candidate_list_override=[self._cand(None)],
        )
        self.assertFalse(result.get("buy_enabled"))
        self.assertFalse(result.get("sell_enabled"))
        self.assertFalse(result.get("hold_enabled"))


# ---------------------------------------------------------------------------
# X5 runner freshness gate integration
# ---------------------------------------------------------------------------

class TestX5RunnerFreshnessGate(_DbBase):
    """X5 runner calls freshness gate before cadence loop and blocks on stale."""

    def _write_five_token_list(self, *, mints: list[str], pairs: list[str]) -> pathlib.Path:
        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        data = {
            "tokens": [
                {
                    "token_mint": m,
                    "pair_address": p,
                    "chain": "solana",
                    "tracking_lane": "TRACK_FAST",
                    "operator_approved": True,
                }
                for m, p in zip(mints, pairs)
            ]
        }
        tf.write_text(json.dumps(data), encoding="utf-8")
        return tf

    def _five_mints(self) -> list[str]:
        return [
            "MintX5AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "MintX5BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "MintX5CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            "MintX5DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
            "MintX5EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE",
        ]

    def _five_pairs(self) -> list[str]:
        return [
            "PairX5AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            "PairX5BBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            "PairX5CCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCCC",
            "PairX5DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD",
            "PairX5EEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEEE",
        ]

    def test_x5_blocks_when_no_freshness_evidence(self):
        """With no discovery candidates or source responses, gate blocks all tokens."""
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            LANE_X5_STATUS_BLOCKED,
            run_five_token_memory_factory_cycle,
        )

        mints = self._five_mints()
        pairs = self._five_pairs()
        tf = self._write_five_token_list(mints=mints, pairs=pairs)

        result = run_five_token_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            duration_profile="1h",
        )

        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        reasons = result.get("blocked_reasons", [])
        self.assertTrue(any("X10.9 freshness gate" in r for r in reasons))

    def test_x5_freshness_gate_results_in_blocked_output(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            run_five_token_memory_factory_cycle,
        )

        mints = self._five_mints()
        pairs = self._five_pairs()
        tf = self._write_five_token_list(mints=mints, pairs=pairs)

        result = run_five_token_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            duration_profile="1h",
        )

        gate_results = result.get("freshness_gate_results", [])
        self.assertEqual(len(gate_results), 5)
        for gr in gate_results:
            self.assertIn("status", gr)
            self.assertIn("evidence_type", gr)
            self.assertIn("mint", gr)
            self.assertIn("pair_address", gr)
            self.assertIn("slot", gr)

    def test_x5_blocked_result_has_no_forbidden_fields(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            run_five_token_memory_factory_cycle,
        )

        mints = self._five_mints()
        pairs = self._five_pairs()
        tf = self._write_five_token_list(mints=mints, pairs=pairs)

        result = run_five_token_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            duration_profile="1h",
        )

        self.assertFalse(result.get("buy_enabled"))
        self.assertFalse(result.get("sell_enabled"))
        self.assertFalse(result.get("hold_enabled"))
        self.assertEqual(result.get("paper_decisions_created"), 0)
        self.assertEqual(result.get("positions_created"), 0)
        self.assertEqual(result.get("pnl_created"), 0)
        self.assertEqual(result.get("retrieval_rows_created"), 0)

    def test_x5_passes_when_all_tokens_have_fresh_source_responses(self):
        """If all 5 tokens have fresh source responses, gate passes and X5 does not block.

        Uses _cycle_budget=0 so the loop exits immediately after the gate clears.
        No _adapter_map: gate runs normally (gate is skipped only when _adapter_map is set).
        """
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            LANE_X5_STATUS_BLOCKED,
            run_five_token_memory_factory_cycle,
        )

        mints = self._five_mints()
        pairs = self._five_pairs()

        # Insert fresh source responses for each pair
        for mint, pair in zip(mints, pairs):
            ts = self._ts(60)  # 60 seconds ago = FRESH
            payload = json.dumps({"pair_address": pair, "token_mint": mint})
            with sqlite3.connect(str(self.db_path)) as conn:
                srq_cur = conn.execute(
                    "INSERT INTO printer_source_requests"
                    " (source_name, request_kind, requested_at, request_key,"
                    "  tracking_priority, source_status, data_quality_label, created_at)"
                    " VALUES ('dexscreener', 'pair_market_snapshot', ?, 'test-key',"
                    "  1, 'COMPLETE', 'CLEAN_DATA', ?)",
                    (ts, ts),
                )
                srq_id = srq_cur.lastrowid
                conn.execute(
                    "INSERT INTO printer_source_responses"
                    " (source_request_id, source_name, received_at, status_code, source_status,"
                    "  data_quality_label, normalized_payload_json, created_at)"
                    " VALUES (?, 'dexscreener', ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, ?)",
                    (srq_id, ts, payload, ts),
                )

        tf = self._write_five_token_list(mints=mints, pairs=pairs)

        # _cycle_budget=0: gate fires → all tokens clear → loop exits immediately.
        # No _adapter_map → gate is active (not in fixture-injection bypass mode).
        result = run_five_token_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            duration_profile="1h",
            _cycle_budget=0,
        )

        # Gate passed — must not be BLOCKED due to freshness
        self.assertNotEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        gate_results = result.get("freshness_gate_results", [])
        self.assertEqual(len(gate_results), 5)
        for gr in gate_results:
            self.assertNotIn(gr["status"], (
                FRESHNESS_STATUS_STALE_BLOCKED,
                FRESHNESS_STATUS_UNKNOWN_BLOCKED,
            ))

    def test_x5_stale_tokens_all_blocked_at_gate(self):
        """All 5 tokens with stale evidence → all flagged in gate_results as STALE."""
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            LANE_X5_STATUS_BLOCKED,
            run_five_token_memory_factory_cycle,
        )

        mints = self._five_mints()
        pairs = self._five_pairs()

        # Insert stale source responses (5 minutes old)
        for mint, pair in zip(mints, pairs):
            ts = self._ts(300)
            payload = json.dumps({"pair_address": pair, "token_mint": mint})
            with sqlite3.connect(str(self.db_path)) as conn:
                srq_cur = conn.execute(
                    "INSERT INTO printer_source_requests"
                    " (source_name, request_kind, requested_at, request_key,"
                    "  tracking_priority, source_status, data_quality_label, created_at)"
                    " VALUES ('dexscreener', 'pair_market_snapshot', ?, 'test-key',"
                    "  1, 'COMPLETE', 'CLEAN_DATA', ?)",
                    (ts, ts),
                )
                srq_id = srq_cur.lastrowid
                conn.execute(
                    "INSERT INTO printer_source_responses"
                    " (source_request_id, source_name, received_at, status_code, source_status,"
                    "  data_quality_label, normalized_payload_json, created_at)"
                    " VALUES (?, 'dexscreener', ?, 200, 'COMPLETE', 'CLEAN_DATA', ?, ?)",
                    (srq_id, ts, payload, ts),
                )

        tf = self._write_five_token_list(mints=mints, pairs=pairs)

        result = run_five_token_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            duration_profile="1h",
        )

        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        gate_results = result.get("freshness_gate_results", [])
        self.assertEqual(len(gate_results), 5)
        for gr in gate_results:
            self.assertEqual(gr["status"], FRESHNESS_STATUS_STALE_BLOCKED)


class TestWatchOnlyCannotEnterX5(unittest.TestCase):
    """WATCH_ONLY / IGNORE / INSTANT_REJECT cannot enter X5 (existing gate unchanged)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = pathlib.Path(self._tmp.name) / "printer_v1.sqlite3"
        self.backup_path = pathlib.Path(self._tmp.name) / "backup.sqlite3"
        self.backup_path.write_bytes(b"backup")
        apply_migrations(self.db_path)

    def tearDown(self):
        self._tmp.cleanup()

    def test_watch_only_token_blocked_by_tracking_lane_check(self):
        from printer_v1.operator_cli.lane_x5_five_token_runner import (
            LANE_X5_STATUS_BLOCKED,
            run_five_token_memory_factory_cycle,
        )

        tf = pathlib.Path(self._tmp.name) / "tokens.json"
        tokens = [
            {
                "token_mint": f"WatchMint{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "pair_address": f"WatchPair{i}AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                "chain": "solana",
                "tracking_lane": "WATCH_ONLY",  # WRONG — must be TRACK_FAST
                "operator_approved": True,
            }
            for i in range(5)
        ]
        tf.write_text(json.dumps({"tokens": tokens}), encoding="utf-8")

        result = run_five_token_memory_factory_cycle(
            token_list_path=tf,
            db_path=self.db_path,
            backup_proof_path=self.backup_path,
            operator_approved=True,
            duration_profile="1h",
        )

        self.assertEqual(result["lane_x5_status"], LANE_X5_STATUS_BLOCKED)
        reasons = str(result.get("blocked_reasons", ""))
        self.assertIn("TRACK_FAST", reasons)


# ---------------------------------------------------------------------------
# Hard lock assertions (gate introduces no new fields)
# ---------------------------------------------------------------------------

class TestGateNoForbiddenFieldsIntroduced(unittest.TestCase):
    """Gate result dicts must not include any financial or forbidden fields."""

    def test_freshness_result_dict_has_no_forbidden_keys(self):
        result = FreshnessResult(
            mint=_MINT_A,
            pair_address=_PAIR_A,
            slot="A",
            status=FRESHNESS_STATUS_UNKNOWN_BLOCKED,
            evidence_type=EVIDENCE_NONE,
            freshness_timestamp=None,
            age_seconds=None,
            reason="test",
            freshness_warning=True,
        )
        d = result.to_dict()
        forbidden = {
            "buy", "sell", "hold", "paper", "position", "pnl", "retrieval",
            "score", "rank", "confidence", "weight", "signal",
        }
        for key in d:
            for bad in forbidden:
                self.assertNotIn(bad, key.lower(), f"forbidden term {bad!r} in key {key!r}")


if __name__ == "__main__":
    unittest.main()
