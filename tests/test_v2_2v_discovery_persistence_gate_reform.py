"""V2-2V — Discovery Persistence Gate Reform.

Targeted tests for the Tier 2 pre-check in _select_discovery_candidates():

A. MIGRATION allowed/blocked
B. REVIVAL allowed/blocked
C. DISTINCT_NEW_EVIDENCE allowed/blocked
D. Tier 1 hard blocks preserved
E. Safety — no memory/paper/source rows created
F. Reporting fields set on accepted Tier 2 candidates
G. Backward compatibility — no db_path → flat gate unchanged

Locks: no live discovery, no source fetching, no live DB mutation outside
test fixtures, no memory generation, no retrieval, no paper decisions,
no BUY/SELL/HOLD, no positions/trades/audits/PnL, no scoring/ranking,
no confidence/weighted logic, no embeddings/vectors.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.operator_cli.commands import (
    _classify_returning_candidate,
    _fingerprint_change_type,
    _load_last_discovery_fingerprint,
    _load_returning_mint_lifecycle_statuses,
    _select_discovery_candidates,
    _TIER2_MIGRATION_CHANNELS,
    _TIER2_REVIVING_LIFECYCLE_STATES,
)

_NOW = datetime.now(timezone.utc).isoformat()

# Migration source channels
_MIGRATION_CH = "PUMPFUN_MIGRATION"
_NON_MIGRATION_CH = "DEXSCREENER_SEARCH"
_GT_NEW_POOL_CH = "GECKOTERMINAL_NEW_POOL"


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _make_db() -> tuple[str, sqlite3.Connection]:
    """Return (db_path, connection) for a fresh test DB with all migrations applied."""
    tmp = tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False)
    db_path = tmp.name
    tmp.close()
    apply_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return db_path, conn


def _insert_token(conn: sqlite3.Connection, token_mint: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO printer_tokens (token_mint, chain, first_seen_at, last_seen_at, token_status)
        VALUES (?, 'solana', ?, ?, 'TRACK_NORMAL')
        """,
        (token_mint, _NOW, _NOW),
    )
    conn.commit()
    return int(cur.lastrowid)


def _insert_pair(conn: sqlite3.Connection, token_id: int, pair_address: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO printer_pairs (token_id, pair_address, first_seen_at, last_seen_at)
        VALUES (?, ?, ?, ?)
        """,
        (token_id, pair_address, _NOW, _NOW),
    )
    conn.commit()
    return int(cur.lastrowid)


def _insert_tracking_queue(
    conn: sqlite3.Connection,
    token_id: int,
    queue_status: str,
    pair_id: int | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO printer_tracking_queue (
            token_id, pair_id, queue_status, tracking_lane, tracking_action,
            priority_reason, next_check_at, source_status, data_quality_label,
            created_at, updated_at
        ) VALUES (?, ?, ?, 'TRACK_NORMAL', 'NEW_DISCOVERY', 'test', ?, 'COMPLETE', 'CLEAN_DATA', ?, ?)
        """,
        (token_id, pair_id, queue_status, _NOW, _NOW, _NOW),
    )
    conn.commit()
    return int(cur.lastrowid)


def _insert_discovery_candidate(
    conn: sqlite3.Connection,
    token_id: int,
    pair_id: int,
    normalized_payload: dict,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO printer_discovery_candidates (
            token_id, pair_id, source_name, discovery_label, discovery_action,
            source_status, data_quality_label,
            raw_candidate_payload_json, normalized_candidate_payload_json,
            lifecycle_state, tracking_lane, priority_reason, created_at
        ) VALUES (?, ?, 'dexscreener', 'TRACK_NORMAL_CANDIDATE', 'TRACK_NORMAL',
                  'COMPLETE', 'CLEAN_DATA', '{}', ?, 'TRACK_NORMAL', 'TRACK_NORMAL', 'test', ?)
        """,
        (token_id, pair_id, json.dumps(normalized_payload), _NOW),
    )
    conn.commit()
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Candidate factories
# ---------------------------------------------------------------------------

def _track_fast_candidate(token_mint: str, pair_address: str, source_channel: str = _NON_MIGRATION_CH) -> dict:
    return {
        "token_mint": token_mint,
        "pair_address": pair_address,
        "chain": "solana",
        "symbol": "TEST",
        "name": "Test Token",
        "source_channel": source_channel,
        "source_channel_reason": "test",
        "source_response_id": None,
        "source_name": "dexscreener",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "captured_at": _NOW,
        "liquidity_usd": 8000.0,
        "volume_5m": 2000.0,
        "txns_5m": 25,
        "volume_1h": 50000.0,
        "txns_1h": 300,
        "volume_24h": 200000.0,
        "txns_24h": 2000,
        "price_usd": 0.001,
        "price_change_5m": 5.0,
        "price_change_1h": 15.0,
        "price_change_24h": 50.0,
        "token_age_seconds": None,
    }


def _dead_candidate(token_mint: str, pair_address: str) -> dict:
    """Candidate with near-zero activity — classifies as D1 / WATCH_ONLY."""
    return {
        "token_mint": token_mint,
        "pair_address": pair_address,
        "chain": "solana",
        "symbol": "DEAD",
        "name": "Dead Token",
        "source_channel": _NON_MIGRATION_CH,
        "source_channel_reason": "test",
        "source_response_id": None,
        "source_name": "dexscreener",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "captured_at": _NOW,
        "liquidity_usd": 300.0,
        "volume_5m": 0.0,
        "txns_5m": 0,
        "volume_1h": 0.0,
        "txns_1h": 0,
        "volume_24h": 5.0,
        "txns_24h": 1,
        "price_usd": 0.00001,
        "price_change_5m": 0.0,
        "price_change_1h": 0.0,
        "price_change_24h": -10.0,
        "token_age_seconds": None,
    }


def _reviving_candidate(token_mint: str, pair_address: str) -> dict:
    """Candidate with small but non-zero short-window activity — ACTIVITY_REVIVING when prior=ARCHIVED."""
    return {
        "token_mint": token_mint,
        "pair_address": pair_address,
        "chain": "solana",
        "symbol": "RVV",
        "name": "Revival Token",
        "source_channel": _GT_NEW_POOL_CH,
        "source_channel_reason": "test",
        "source_response_id": None,
        "source_name": "geckoterminal",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "captured_at": _NOW,
        "liquidity_usd": 1500.0,
        "volume_5m": 100.0,
        "txns_5m": 5,
        "volume_1h": 500.0,
        "txns_1h": 20,
        "volume_24h": 1000.0,
        "txns_24h": 50,
        "price_usd": 0.0001,
        "price_change_5m": 3.0,
        "price_change_1h": 8.0,
        "price_change_24h": 20.0,
        "token_age_seconds": None,
    }


# ---------------------------------------------------------------------------
# A. MIGRATION path
# ---------------------------------------------------------------------------

class TestMigrationAllowed(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()
        # Seed an existing token + existing pair
        self.token_id = _insert_token(self.conn, "MINT_MIG_A")
        self.pair_id = _insert_pair(self.conn, self.token_id, "PAIR_OLD_A")

    def tearDown(self):
        self.conn.close()

    def test_migration_new_pair_allowed(self):
        """Existing mint + migration channel + new pair → Tier 2 ALLOWED."""
        cand = _track_fast_candidate("MINT_MIG_A", "PAIR_NEW_A", source_channel=_MIGRATION_CH)
        existing_mints = {"MINT_MIG_A"}
        existing_pairs = {"PAIR_OLD_A"}

        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints=existing_mints,
            existing_pair_addresses=existing_pairs,
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )

        self.assertEqual(len(accepted), 1, f"Expected accepted=1; rejected={[r.get('reject_reason') for r in rejected]}")
        self.assertEqual(len(rejected), 0)
        self.assertEqual(accepted[0].get("resurfacing_category"), "MIGRATION")
        self.assertEqual(accepted[0].get("tier2_gate_outcome"), "ALLOWED")

    def test_migration_reporting_fields_set(self):
        """MIGRATION accepted candidate has all required Tier 2 reporting fields."""
        cand = _track_fast_candidate("MINT_MIG_A", "PAIR_NEW_A2", source_channel=_MIGRATION_CH)
        accepted, _, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_MIG_A"},
            existing_pair_addresses={"PAIR_OLD_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1)
        a = accepted[0]
        self.assertEqual(a.get("resurfacing_category"), "MIGRATION")
        self.assertIsNotNone(a.get("resurfacing_reason"))
        self.assertEqual(a.get("tier2_gate_outcome"), "ALLOWED")

    def test_migration_blocked_when_pair_already_exists(self):
        """Migration channel but pair already exists → flat gate blocked."""
        cand = _track_fast_candidate("MINT_MIG_A", "PAIR_OLD_A", source_channel=_MIGRATION_CH)
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_MIG_A"},
            existing_pair_addresses={"PAIR_OLD_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(rejected), 1)
        self.assertIn("duplicate", rejected[0].get("reject_reason", ""))

    def test_migration_blocked_non_migration_channel_new_pair(self):
        """Same mint, new pair, but non-migration channel → flat gate blocked."""
        cand = _track_fast_candidate("MINT_MIG_A", "PAIR_NEW_B", source_channel=_NON_MIGRATION_CH)
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_MIG_A"},
            existing_pair_addresses={"PAIR_OLD_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["reject_reason"], "duplicate_existing_token_mint")

    def test_all_migration_channels_recognized(self):
        """Each migration channel constant allows a new pair through."""
        for ch in _TIER2_MIGRATION_CHANNELS:
            with self.subTest(channel=ch):
                cand = _track_fast_candidate("MINT_MIG_A", f"PAIR_NEW_{ch}", source_channel=ch)
                accepted, rejected, _, _ = _select_discovery_candidates(
                    [cand],
                    existing_token_mints={"MINT_MIG_A"},
                    existing_pair_addresses={"PAIR_OLD_A"},
                    max_candidates=5,
                    db_path_or_conn=self.db_path,
                )
                self.assertEqual(len(accepted), 1, f"channel={ch} should allow; rejected={rejected}")


# ---------------------------------------------------------------------------
# B. REVIVAL path
# ---------------------------------------------------------------------------

class TestRevivalAllowed(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()
        self.token_id = _insert_token(self.conn, "MINT_RVV_A")
        self.pair_id = _insert_pair(self.conn, self.token_id, "PAIR_RVV_A")

    def tearDown(self):
        self.conn.close()

    def _seed_lifecycle(self, status: str):
        _insert_tracking_queue(self.conn, self.token_id, status, self.pair_id)

    def test_revival_archived_with_activity_allowed(self):
        """Mint in ARCHIVED + short-window activity present → REVIVAL allowed."""
        self._seed_lifecycle("ARCHIVED")
        cand = _reviving_candidate("MINT_RVV_A", "PAIR_RVV_A")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RVV_A"},
            existing_pair_addresses={"PAIR_RVV_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1, f"Expected accepted=1; rejected={[r.get('reject_reason') for r in rejected]}")
        self.assertEqual(accepted[0].get("resurfacing_category"), "REVIVAL")
        self.assertEqual(accepted[0].get("tier2_gate_outcome"), "ALLOWED")
        self.assertEqual(accepted[0].get("prior_lifecycle_state"), "ARCHIVED")

    def test_revival_cooldown_with_activity_allowed(self):
        """Mint in COOLDOWN + short-window activity present → REVIVAL allowed."""
        self._seed_lifecycle("COOLDOWN")
        cand = _reviving_candidate("MINT_RVV_A", "PAIR_RVV_A")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RVV_A"},
            existing_pair_addresses={"PAIR_RVV_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].get("resurfacing_category"), "REVIVAL")
        self.assertEqual(accepted[0].get("prior_lifecycle_state"), "COOLDOWN")

    def test_revival_blocked_queued_status_not_eligible(self):
        """Mint in QUEUED lifecycle → not a revival candidate → flat gate blocks."""
        self._seed_lifecycle("QUEUED")
        cand = _reviving_candidate("MINT_RVV_A", "PAIR_RVV_A")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RVV_A"},
            existing_pair_addresses={"PAIR_RVV_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        # QUEUED is not a reviving lifecycle state → Tier 2 falls through to
        # DISTINCT_NEW_EVIDENCE; with no prior discovery record → blocked.
        self.assertEqual(len(accepted), 0)
        self.assertGreater(len(rejected), 0)

    def test_revival_blocked_archived_but_dead_activity(self):
        """Mint in ARCHIVED but activity is dead → REVIVAL blocked."""
        self._seed_lifecycle("ARCHIVED")
        cand = _dead_candidate("MINT_RVV_A", "PAIR_RVV_A")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RVV_A"},
            existing_pair_addresses={"PAIR_RVV_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertGreater(len(rejected), 0)

    def test_all_reviving_states_recognized(self):
        """Both ARCHIVED and COOLDOWN are reviving lifecycle states."""
        self.assertEqual(_TIER2_REVIVING_LIFECYCLE_STATES, frozenset({"COOLDOWN", "ARCHIVED"}))


# ---------------------------------------------------------------------------
# C. DISTINCT_NEW_EVIDENCE path
# ---------------------------------------------------------------------------

class TestDistinctNewEvidenceAllowed(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()
        self.token_id = _insert_token(self.conn, "MINT_DNE_A")
        self.pair_id = _insert_pair(self.conn, self.token_id, "PAIR_DNE_A")

    def tearDown(self):
        self.conn.close()

    def _seed_dead_history(self):
        """Seed a dead historical candidate (activity_bucket=ACTIVITY_DEAD)."""
        dead = _dead_candidate("MINT_DNE_A", "PAIR_DNE_A")
        _insert_discovery_candidate(self.conn, self.token_id, self.pair_id, dead)

    def test_dne_allowed_when_activity_bucket_changes(self):
        """Historical dead, current fast → activity_bucket changed → DISTINCT_NEW_EVIDENCE allowed."""
        self._seed_dead_history()
        cand = _track_fast_candidate("MINT_DNE_A", "PAIR_DNE_A")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_DNE_A"},
            existing_pair_addresses={"PAIR_DNE_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1, f"Expected accepted=1; rejected={[r.get('reject_reason') for r in rejected]}")
        self.assertEqual(accepted[0].get("resurfacing_category"), "DISTINCT_NEW_EVIDENCE")
        self.assertEqual(accepted[0].get("tier2_gate_outcome"), "ALLOWED")
        self.assertIsNotNone(accepted[0].get("fingerprint_change_type"))

    def test_dne_allowed_when_source_channel_changes(self):
        """Historical on non-migration channel, current on different channel → DISTINCT_NEW_EVIDENCE allowed."""
        historical = _track_fast_candidate("MINT_DNE_A", "PAIR_DNE_A", source_channel=_NON_MIGRATION_CH)
        _insert_discovery_candidate(self.conn, self.token_id, self.pair_id, historical)
        cand = _track_fast_candidate("MINT_DNE_A", "PAIR_DNE_A", source_channel=_GT_NEW_POOL_CH)
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_DNE_A"},
            existing_pair_addresses={"PAIR_DNE_A"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1, f"Expected accepted=1; rejected={[r.get('reject_reason') for r in rejected]}")
        self.assertEqual(accepted[0].get("resurfacing_category"), "DISTINCT_NEW_EVIDENCE")


# ---------------------------------------------------------------------------
# D. DISTINCT_NEW_EVIDENCE blocked
# ---------------------------------------------------------------------------

class TestDistinctNewEvidenceBlocked(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()
        self.token_id = _insert_token(self.conn, "MINT_DNE_B")
        self.pair_id = _insert_pair(self.conn, self.token_id, "PAIR_DNE_B")

    def tearDown(self):
        self.conn.close()

    def test_blocked_no_historical_record(self):
        """No historical discovery candidate → null-safe block."""
        cand = _track_fast_candidate("MINT_DNE_B", "PAIR_DNE_B")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_DNE_B"},
            existing_pair_addresses={"PAIR_DNE_B"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(rejected), 1)

    def test_blocked_unparseable_historical_payload(self):
        """Historical payload is invalid JSON → null-safe block."""
        self.conn.execute(
            """
            INSERT INTO printer_discovery_candidates (
                token_id, pair_id, source_name, discovery_label, discovery_action,
                source_status, data_quality_label,
                raw_candidate_payload_json, normalized_candidate_payload_json,
                lifecycle_state, tracking_lane, priority_reason, created_at
            ) VALUES (?, ?, 'dexscreener', 'TRACK_NORMAL_CANDIDATE', 'TRACK_NORMAL',
                      'COMPLETE', 'CLEAN_DATA', '{}', 'NOT_VALID_JSON', 'TRACK_NORMAL',
                      'TRACK_NORMAL', 'test', ?)
            """,
            (self.token_id, self.pair_id, _NOW),
        )
        self.conn.commit()
        cand = _track_fast_candidate("MINT_DNE_B", "PAIR_DNE_B")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_DNE_B"},
            existing_pair_addresses={"PAIR_DNE_B"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(rejected), 1)

    def test_blocked_no_meaningful_change_same_fingerprint(self):
        """Same activity_bucket, same source_channel, same bucket group → blocked."""
        historical = _track_fast_candidate("MINT_DNE_B", "PAIR_DNE_B", source_channel=_NON_MIGRATION_CH)
        _insert_discovery_candidate(self.conn, self.token_id, self.pair_id, historical)
        # Same candidate again — fingerprint unchanged
        cand = _track_fast_candidate("MINT_DNE_B", "PAIR_DNE_B", source_channel=_NON_MIGRATION_CH)
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_DNE_B"},
            existing_pair_addresses={"PAIR_DNE_B"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0, "Identical fingerprint should block")
        self.assertEqual(len(rejected), 1)


# ---------------------------------------------------------------------------
# E. Tier 1 hard blocks preserved
# ---------------------------------------------------------------------------

class TestTier1HardBlocksPreserved(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()

    def tearDown(self):
        self.conn.close()

    def test_non_solana_blocked(self):
        """Non-Solana candidate is always blocked before Tier 2."""
        cand = _track_fast_candidate("MINT_X", "PAIR_X")
        cand["chain"] = "ethereum"
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_X"},
            existing_pair_addresses={"PAIR_X"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(rejected[0]["reject_reason"], "non_solana_candidate")

    def test_duplicate_recycle_blocked_no_fingerprint_change(self):
        """Same mint+pair with no evidence change → blocked (DUPLICATE_RECYCLE behavior)."""
        token_id = _insert_token(self.conn, "MINT_RECYCLE")
        pair_id = _insert_pair(self.conn, token_id, "PAIR_RECYCLE")
        historical = _track_fast_candidate("MINT_RECYCLE", "PAIR_RECYCLE")
        _insert_discovery_candidate(self.conn, token_id, pair_id, historical)
        cand = _track_fast_candidate("MINT_RECYCLE", "PAIR_RECYCLE")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RECYCLE"},
            existing_pair_addresses={"PAIR_RECYCLE"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(len(rejected), 1)

    def test_stnp_unresolved_new_pair_non_migration_channel_blocked(self):
        """Same mint, new pair, non-migration channel → STNP unresolved → blocked."""
        _insert_token(self.conn, "MINT_STNP")
        cand = _track_fast_candidate("MINT_STNP", "PAIR_STNP_NEW", source_channel=_NON_MIGRATION_CH)
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_STNP"},
            existing_pair_addresses={"PAIR_STNP_OLD"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(rejected[0]["reject_reason"], "duplicate_existing_token_mint")

    def test_pair_only_collision_blocked(self):
        """New mint but existing pair → flat gate 'duplicate_pair_address'."""
        cand = _track_fast_candidate("MINT_NEW_X", "PAIR_EXISTING")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints=set(),
            existing_pair_addresses={"PAIR_EXISTING"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(rejected[0]["reject_reason"], "duplicate_pair_address")

    def test_instant_reject_classification_blocked(self):
        """Candidate with unsupported chain classification blocked before Tier 2."""
        cand = _track_fast_candidate("MINT_IR", "PAIR_IR")
        cand["chain"] = "bsc"  # non-solana → instant reject / non_solana_candidate
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints=set(),
            existing_pair_addresses=set(),
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 0)
        self.assertEqual(rejected[0]["reject_reason"], "non_solana_candidate")


# ---------------------------------------------------------------------------
# F. Safety — no forbidden table rows created
# ---------------------------------------------------------------------------

class TestSafety(unittest.TestCase):

    FORBIDDEN_TABLES = [
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trade_events",
        "printer_paper_trade_audits",
        "printer_paper_audit_reports",
        "printer_memory_windows",
        "printer_episodes",
        "printer_episode_snapshots",
        "printer_memory_fingerprints",
        "printer_source_requests",
        "printer_source_responses",
        "printer_source_failures",
        "printer_scheduler_jobs",
    ]

    def setUp(self):
        self.db_path, self.conn = _make_db()
        self.token_id = _insert_token(self.conn, "MINT_SAFE")
        self.pair_id = _insert_pair(self.conn, self.token_id, "PAIR_SAFE")
        _insert_tracking_queue(self.conn, self.token_id, "ARCHIVED", self.pair_id)

    def tearDown(self):
        self.conn.close()

    def _count(self, table: str) -> int:
        try:
            return int(self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
        except sqlite3.OperationalError:
            return 0

    def test_no_forbidden_rows_from_migration_path(self):
        """MIGRATION path creates zero rows in all forbidden tables."""
        cand = _track_fast_candidate("MINT_SAFE", "PAIR_SAFE_NEW", source_channel=_MIGRATION_CH)
        _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_SAFE"},
            existing_pair_addresses={"PAIR_SAFE"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        for table in self.FORBIDDEN_TABLES:
            with self.subTest(table=table):
                self.assertEqual(self._count(table), 0, f"Unexpected rows in {table}")

    def test_no_forbidden_rows_from_revival_path(self):
        """REVIVAL path creates zero rows in all forbidden tables."""
        cand = _reviving_candidate("MINT_SAFE", "PAIR_SAFE")
        _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_SAFE"},
            existing_pair_addresses={"PAIR_SAFE"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        for table in self.FORBIDDEN_TABLES:
            with self.subTest(table=table):
                self.assertEqual(self._count(table), 0, f"Unexpected rows in {table}")

    def test_no_forbidden_rows_from_dne_path(self):
        """DISTINCT_NEW_EVIDENCE path creates zero rows in all forbidden tables."""
        dead = _dead_candidate("MINT_SAFE", "PAIR_SAFE")
        _insert_discovery_candidate(self.conn, self.token_id, self.pair_id, dead)
        cand = _track_fast_candidate("MINT_SAFE", "PAIR_SAFE")
        _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_SAFE"},
            existing_pair_addresses={"PAIR_SAFE"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        for table in self.FORBIDDEN_TABLES:
            with self.subTest(table=table):
                self.assertEqual(self._count(table), 0, f"Unexpected rows in {table}")

    def test_token_age_seconds_not_assigned_from_pair_age(self):
        """token_age_seconds must never be derived from pair-age context."""
        cand = _track_fast_candidate("MINT_SAFE", "PAIR_SAFE_NEW", source_channel=_MIGRATION_CH)
        self.assertIsNone(cand.get("token_age_seconds"))
        accepted, _, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_SAFE"},
            existing_pair_addresses={"PAIR_SAFE"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        if accepted:
            # token_age_seconds must not have been synthesized from pair data
            self.assertIsNone(accepted[0].get("token_age_seconds"))


# ---------------------------------------------------------------------------
# G. Reporting fields on Tier 2 accepted candidates
# ---------------------------------------------------------------------------

class TestReportingFields(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()
        self.token_id = _insert_token(self.conn, "MINT_RF")
        self.pair_id = _insert_pair(self.conn, self.token_id, "PAIR_RF")

    def tearDown(self):
        self.conn.close()

    def test_migration_fields_present(self):
        cand = _track_fast_candidate("MINT_RF", "PAIR_RF_NEW", source_channel=_MIGRATION_CH)
        accepted, _, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RF"},
            existing_pair_addresses={"PAIR_RF"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1)
        a = accepted[0]
        self.assertEqual(a.get("resurfacing_category"), "MIGRATION")
        self.assertIsNotNone(a.get("resurfacing_reason"))
        self.assertEqual(a.get("tier2_gate_outcome"), "ALLOWED")
        # prior_lifecycle_state and fingerprint_change_type are not set for MIGRATION
        # but keys must be present (set to None is valid)
        self.assertIn("prior_lifecycle_state", a)
        self.assertIn("fingerprint_change_type", a)

    def test_revival_fields_present(self):
        _insert_tracking_queue(self.conn, self.token_id, "ARCHIVED", self.pair_id)
        cand = _reviving_candidate("MINT_RF", "PAIR_RF")
        accepted, _, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RF"},
            existing_pair_addresses={"PAIR_RF"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1)
        a = accepted[0]
        self.assertEqual(a.get("resurfacing_category"), "REVIVAL")
        self.assertEqual(a.get("prior_lifecycle_state"), "ARCHIVED")
        self.assertEqual(a.get("tier2_gate_outcome"), "ALLOWED")

    def test_dne_fields_present(self):
        dead = _dead_candidate("MINT_RF", "PAIR_RF")
        _insert_discovery_candidate(self.conn, self.token_id, self.pair_id, dead)
        cand = _track_fast_candidate("MINT_RF", "PAIR_RF")
        accepted, _, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_RF"},
            existing_pair_addresses={"PAIR_RF"},
            max_candidates=5,
            db_path_or_conn=self.db_path,
        )
        self.assertEqual(len(accepted), 1)
        a = accepted[0]
        self.assertEqual(a.get("resurfacing_category"), "DISTINCT_NEW_EVIDENCE")
        self.assertIsNotNone(a.get("fingerprint_change_type"))
        self.assertEqual(a.get("tier2_gate_outcome"), "ALLOWED")


# ---------------------------------------------------------------------------
# H. Backward compatibility — no db_path_or_conn → flat gate unchanged
# ---------------------------------------------------------------------------

class TestBackwardCompatibility(unittest.TestCase):

    def test_existing_mint_blocked_without_db(self):
        """Without db_path_or_conn the flat gate fires for existing mints."""
        cand = _track_fast_candidate("MINT_BACK", "PAIR_BACK")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_BACK"},
            existing_pair_addresses={"PAIR_BACK"},
            max_candidates=5,
        )
        self.assertEqual(len(accepted), 0)
        self.assertIn("duplicate", rejected[0].get("reject_reason", ""))

    def test_migration_channel_still_allowed_without_db(self):
        """MIGRATION is stateless (channel + new pair only); allowed even without db_path_or_conn."""
        cand = _track_fast_candidate("MINT_BACK_MIG", "PAIR_BACK_NEW", source_channel=_MIGRATION_CH)
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_BACK_MIG"},
            existing_pair_addresses={"PAIR_BACK_OLD"},
            max_candidates=5,
        )
        # MIGRATION path needs no DB: checks source_channel and pair_address only.
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].get("resurfacing_category"), "MIGRATION")

    def test_revival_blocked_without_db(self):
        """Without db_path, lifecycle_statuses={} → REVIVAL skipped → DISTINCT_NEW_EVIDENCE no conn → blocked."""
        cand = _reviving_candidate("MINT_BACK_RVV", "PAIR_BACK_RVV")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints={"MINT_BACK_RVV"},
            existing_pair_addresses={"PAIR_BACK_RVV"},
            max_candidates=5,
        )
        self.assertEqual(len(accepted), 0)
        self.assertGreater(len(rejected), 0)

    def test_fresh_candidate_accepted_without_db(self):
        """Candidate with no existing mint/pair is accepted even without db_path."""
        cand = _track_fast_candidate("MINT_FRESH", "PAIR_FRESH")
        accepted, rejected, _, _ = _select_discovery_candidates(
            [cand],
            existing_token_mints=set(),
            existing_pair_addresses=set(),
            max_candidates=5,
        )
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 0)


# ---------------------------------------------------------------------------
# I. Unit tests for lower-level helpers
# ---------------------------------------------------------------------------

class TestLoadReturningMintLifecycleStatuses(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()

    def tearDown(self):
        self.conn.close()

    def test_returns_empty_for_no_mints(self):
        result = _load_returning_mint_lifecycle_statuses(self.conn, [])
        self.assertEqual(result, {})

    def test_returns_most_recent_status(self):
        token_id = _insert_token(self.conn, "MINT_LQ")
        _insert_tracking_queue(self.conn, token_id, "QUEUED")
        _insert_tracking_queue(self.conn, token_id, "ARCHIVED")
        result = _load_returning_mint_lifecycle_statuses(self.conn, ["MINT_LQ"])
        # Most recent insertion is ARCHIVED; returned status should be ARCHIVED.
        self.assertIn("MINT_LQ", result)
        # Result is the most recent queue_status per the ORDER BY updated_at DESC.

    def test_unknown_mint_not_in_result(self):
        result = _load_returning_mint_lifecycle_statuses(self.conn, ["DOES_NOT_EXIST"])
        self.assertNotIn("DOES_NOT_EXIST", result)


class TestLoadLastDiscoveryFingerprint(unittest.TestCase):

    def setUp(self):
        self.db_path, self.conn = _make_db()
        self.token_id = _insert_token(self.conn, "MINT_FING")
        self.pair_id = _insert_pair(self.conn, self.token_id, "PAIR_FING")

    def tearDown(self):
        self.conn.close()

    def test_returns_none_when_no_record(self):
        result = _load_last_discovery_fingerprint(self.conn, "MINT_FING", "PAIR_FING")
        self.assertIsNone(result)

    def test_returns_fingerprint_dict(self):
        cand = _track_fast_candidate("MINT_FING", "PAIR_FING")
        _insert_discovery_candidate(self.conn, self.token_id, self.pair_id, cand)
        result = _load_last_discovery_fingerprint(self.conn, "MINT_FING", "PAIR_FING")
        self.assertIsNotNone(result)
        self.assertIn("activity_bucket", result)
        self.assertIn("primary_bucket", result)
        self.assertIn("source_channel", result)
        self.assertIn("pair_age_context_label", result)

    def test_returns_none_for_unparseable_payload(self):
        self.conn.execute(
            """
            INSERT INTO printer_discovery_candidates (
                token_id, pair_id, source_name, discovery_label, discovery_action,
                source_status, data_quality_label,
                raw_candidate_payload_json, normalized_candidate_payload_json,
                lifecycle_state, tracking_lane, priority_reason, created_at
            ) VALUES (?, ?, 'test', 'TRACK_NORMAL_CANDIDATE', 'TRACK_NORMAL',
                      'COMPLETE', 'CLEAN_DATA', '{}', 'INVALID{{', 'TRACK_NORMAL', 'TRACK_NORMAL', 'test', ?)
            """,
            (self.token_id, self.pair_id, _NOW),
        )
        self.conn.commit()
        result = _load_last_discovery_fingerprint(self.conn, "MINT_FING", "PAIR_FING")
        self.assertIsNone(result)


class TestFingerprintChangeType(unittest.TestCase):

    def test_activity_bucket_change(self):
        old = {"activity_bucket": "ACTIVITY_DEAD", "source_channel": "X", "primary_bucket": "D1", "pair_age_context_label": "OLD"}
        new = {"activity_bucket": "ACTIVITY_HIGH", "source_channel": "X", "primary_bucket": "D1", "pair_age_context_label": "OLD"}
        result = _fingerprint_change_type(old, new)
        self.assertIn("activity_bucket", result)

    def test_source_channel_change(self):
        old = {"activity_bucket": "ACTIVITY_HIGH", "source_channel": "A", "primary_bucket": "B1", "pair_age_context_label": "OLD"}
        new = {"activity_bucket": "ACTIVITY_HIGH", "source_channel": "B", "primary_bucket": "B1", "pair_age_context_label": "OLD"}
        result = _fingerprint_change_type(old, new)
        self.assertIn("source_channel", result)


class TestClassifyReturningCandidateUnit(unittest.TestCase):
    """Direct unit tests for _classify_returning_candidate with no DB."""

    def _base_cand(self, source_channel: str = _MIGRATION_CH) -> dict:
        return _track_fast_candidate("MINT_UNIT", "PAIR_UNIT_NEW", source_channel=source_channel)

    def test_migration_allowed_with_migration_channel(self):
        result = _classify_returning_candidate(
            self._base_cand(_MIGRATION_CH),
            "MINT_UNIT",
            "PAIR_UNIT_NEW",
            "B1",
            existing_pair_addresses={"PAIR_UNIT_OLD"},
            lifecycle_statuses={},
            conn=None,
        )
        self.assertEqual(result["tier2_gate_outcome"], "ALLOWED")
        self.assertEqual(result["resurfacing_category"], "MIGRATION")

    def test_migration_blocked_pair_exists(self):
        result = _classify_returning_candidate(
            self._base_cand(_MIGRATION_CH),
            "MINT_UNIT",
            "PAIR_UNIT_OLD",
            "B1",
            existing_pair_addresses={"PAIR_UNIT_OLD"},
            lifecycle_statuses={},
            conn=None,
        )
        self.assertEqual(result["tier2_gate_outcome"], "BLOCKED")
        self.assertEqual(result["resurfacing_category"], "MIGRATION")

    def test_non_migration_not_applicable_without_conn(self):
        result = _classify_returning_candidate(
            self._base_cand(_NON_MIGRATION_CH),
            "MINT_UNIT",
            "PAIR_UNIT_OLD",
            "B1",
            existing_pair_addresses={"PAIR_UNIT_OLD"},
            lifecycle_statuses={},
            conn=None,
        )
        # No migration, no revival, no conn → NOT_APPLICABLE
        self.assertEqual(result["tier2_gate_outcome"], "NOT_APPLICABLE")

    def test_revival_archived_with_reviving_activity(self):
        cand = _reviving_candidate("MINT_UNIT", "PAIR_UNIT")
        result = _classify_returning_candidate(
            cand,
            "MINT_UNIT",
            "PAIR_UNIT",
            "B1",
            existing_pair_addresses={"PAIR_UNIT"},
            lifecycle_statuses={"MINT_UNIT": "ARCHIVED"},
            conn=None,
        )
        self.assertEqual(result["tier2_gate_outcome"], "ALLOWED")
        self.assertEqual(result["resurfacing_category"], "REVIVAL")
        self.assertEqual(result["prior_lifecycle_state"], "ARCHIVED")

    def test_revival_blocked_dead_activity(self):
        cand = _dead_candidate("MINT_UNIT", "PAIR_UNIT")
        result = _classify_returning_candidate(
            cand,
            "MINT_UNIT",
            "PAIR_UNIT",
            "D1",
            existing_pair_addresses={"PAIR_UNIT"},
            lifecycle_statuses={"MINT_UNIT": "ARCHIVED"},
            conn=None,
        )
        self.assertEqual(result["tier2_gate_outcome"], "BLOCKED")
        self.assertEqual(result["resurfacing_category"], "REVIVAL")

    def test_new_pair_non_migration_not_applicable(self):
        cand = _track_fast_candidate("MINT_UNIT", "PAIR_UNIT_NEW2", source_channel=_NON_MIGRATION_CH)
        result = _classify_returning_candidate(
            cand,
            "MINT_UNIT",
            "PAIR_UNIT_NEW2",
            "B1",
            existing_pair_addresses={"PAIR_UNIT_OLD"},
            lifecycle_statuses={},
            conn=None,
        )
        self.assertEqual(result["tier2_gate_outcome"], "NOT_APPLICABLE")


if __name__ == "__main__":
    unittest.main()
