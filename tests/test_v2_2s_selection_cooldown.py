"""V2-2S cross-batch selection cooldown unit tests.

Tests cover:
  - Token-level selection cooldown: blocked in batches 2 and 3, allowed at 4
  - Pair-level selection cooldown: independent from token cooldown
  - Evidence identity fingerprint: 4 categorical fields, no scores or floats
  - Fingerprint meaningful-change detection
  - Rotation state persistence via persist_selection_batch()
  - selection_count increment on reselection
  - Rejected items not written to rotation state
  - Batch seq monotonically increasing
  - Safety: no financial paths, no token-age mutation

All tests use fixtures only. No live discovery, source fetching, DB mutation
against the live DB, memory generation, retrieval, paper decisions, or
financial rows. No scores, ranks, confidence, or weighted logic.
"""

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.discovery.selection_batch import (
    ITEM_STATUS_SELECTED,
    ITEM_STATUS_REJECTED,
    REJECTION_TOKEN_SELECTION_COOLDOWN,
    REJECTION_PAIR_SELECTION_COOLDOWN,
    assign_bucket,
    build_batch_item,
    persist_selection_batch,
    compute_evidence_identity_fingerprint,
    fingerprint_change_is_meaningful,
    check_token_selection_cooldown,
    check_pair_selection_cooldown,
    record_selection_rotation_state,
    apply_selection_cooldown_gates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> sqlite3.Connection:
    """Return a named-file SQLite connection with all migrations applied."""
    with tempfile.NamedTemporaryFile(suffix=".sqlite3", delete=False) as f:
        db_path = f.name
    apply_migrations(db_path)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _fast_candidate(**overrides: object) -> dict:
    base = {
        "token_mint": "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "pair_address": "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        "chain": "solana",
        "source_name": "dexscreener",
        "source_channel": "DEXSCREENER_SEARCH",
        "tracking_lane": "TRACK_FAST",
        "discovery_action": "TRACK_FAST",
        "liquidity_usd": 10_000.0,
        "volume_5m": 2_000.0,
        "volume_1h": 20_000.0,
        "volume_24h": 80_000.0,
        "txns_5m": 20,
        "txns_1h": 80,
        "txns_24h": 300,
        "price_usd": 0.001,
        "price_change_5m": 5.0,
        "price_change_1h": 15.0,
        "price_change_24h": 30.0,
        "token_age_seconds": 600.0,
        "pair_age_seconds": None,
        "safety_label": "SAFE",
        "source_response_id": 1,
        "pair_age_context_label": None,
        "token_age_evidence_tier": None,
    }
    base.update(overrides)
    return base


def _make_selected_item(candidate: dict) -> dict:
    """Build a SELECTED batch item from a candidate."""
    bucket, bname = assign_bucket(candidate)
    return build_batch_item(
        candidate,
        item_status=ITEM_STATUS_SELECTED,
        primary_bucket=bucket,
        bucket_name=bname,
        tracking_lane=candidate.get("tracking_lane", "TRACK_FAST"),
        operator_approved=True,
    )


def _seed_rotation_state(
    conn: sqlite3.Connection,
    token_mint: str,
    pair_address: str,
    batch_seq: int,
    batch_id: str = "SEED_BATCH",
    source_channel: str = "DEXSCREENER_SEARCH",
) -> None:
    """Insert a rotation-state row directly to set up cooldown fixtures."""
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    fp_json = json.dumps({
        "activity_bucket": "ACTIVITY_HIGH",
        "pair_age_context_label": None,
        "primary_bucket": "A1",
        "source_channel": source_channel,
    }, sort_keys=True)
    conn.execute(
        """
        INSERT INTO printer_selection_rotation_state
          (token_mint, pair_address,
           last_selected_batch_id, last_selected_batch_seq, last_selected_at,
           last_evidence_fingerprint_json, selection_count,
           created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?)
        """,
        (token_mint, pair_address, batch_id, batch_seq, now, fp_json, now, now),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Token-level selection cooldown
# ---------------------------------------------------------------------------

class TestTokenSelectionCooldown(unittest.TestCase):

    def test_no_prior_selection_returns_ok(self):
        conn = _make_db()
        ok, reason = check_token_selection_cooldown(conn, "MINT_UNKNOWN", current_batch_seq=1)
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        conn.close()

    def test_selected_at_seq_1_blocked_at_seq_2(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=2)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_blocked_at_seq_3(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=3)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_allowed_at_seq_4_after_window_3(self):
        # V2-2R Proof 1: selected at 1, allowed at 4 (batches_since=3, not <3).
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=4)
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        conn.close()

    def test_different_mint_not_affected(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_token_selection_cooldown(conn, "MINT_B", current_batch_seq=2)
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        conn.close()

    def test_custom_window_respected(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        # With window=5, batches_since=4 is still < 5 → blocked.
        ok, reason = check_token_selection_cooldown(
            conn, "MINT_A", current_batch_seq=5, cooldown_window=5
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_window_1_allows_immediately_next_batch(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        # window=1: batches_since=1, 1 < 1 is False → allowed at seq 2.
        ok, reason = check_token_selection_cooldown(
            conn, "MINT_A", current_batch_seq=2, cooldown_window=1
        )
        self.assertTrue(ok)
        conn.close()

    def test_returns_tuple_of_bool_and_str(self):
        conn = _make_db()
        result = check_token_selection_cooldown(conn, "MINT_X", current_batch_seq=1)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)
        conn.close()


# ---------------------------------------------------------------------------
# Pair-level selection cooldown
# ---------------------------------------------------------------------------

class TestPairSelectionCooldown(unittest.TestCase):

    def test_no_prior_selection_returns_ok(self):
        conn = _make_db()
        ok, reason = check_pair_selection_cooldown(conn, "PAIR_UNKNOWN", current_batch_seq=1)
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        conn.close()

    def test_same_pair_blocked_during_cooldown(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_pair_selection_cooldown(conn, "PAIR_A", current_batch_seq=2)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_PAIR_SELECTION_COOLDOWN)
        conn.close()

    def test_pair_allowed_after_cooldown_window(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_pair_selection_cooldown(conn, "PAIR_A", current_batch_seq=4)
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        conn.close()

    def test_new_pair_not_affected_by_pair_cooldown(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_pair_selection_cooldown(conn, "PAIR_B", current_batch_seq=2)
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        conn.close()

    def test_token_cooldown_independent_from_pair_cooldown(self):
        # PAIR_B has no pair cooldown, but MINT_A still has token-level cooldown.
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok_pair, _ = check_pair_selection_cooldown(conn, "PAIR_B", current_batch_seq=2)
        ok_token, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=2)
        self.assertTrue(ok_pair)
        self.assertFalse(ok_token)
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_pair_blocked_at_seq_3(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        ok, reason = check_pair_selection_cooldown(conn, "PAIR_A", current_batch_seq=3)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_PAIR_SELECTION_COOLDOWN)
        conn.close()

    def test_returns_tuple_of_bool_and_str(self):
        conn = _make_db()
        result = check_pair_selection_cooldown(conn, "PAIR_X", current_batch_seq=1)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], bool)
        self.assertIsInstance(result[1], str)
        conn.close()


# ---------------------------------------------------------------------------
# Evidence identity fingerprint
# ---------------------------------------------------------------------------

class TestEvidenceIdentityFingerprint(unittest.TestCase):

    def test_fingerprint_has_exactly_four_fields(self):
        candidate = _fast_candidate()
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertEqual(set(fp.keys()), {
            "activity_bucket", "pair_age_context_label", "source_channel", "primary_bucket"
        })

    def test_fingerprint_contains_no_floats(self):
        candidate = _fast_candidate()
        fp = compute_evidence_identity_fingerprint(candidate)
        for key, val in fp.items():
            self.assertNotIsInstance(
                val, float, f"Float found in fingerprint key '{key}': {val!r}"
            )

    def test_fingerprint_does_not_contain_token_age_seconds(self):
        candidate = _fast_candidate(token_age_seconds=600.0)
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertNotIn("token_age_seconds", fp)

    def test_fingerprint_does_not_contain_pair_age_seconds(self):
        candidate = _fast_candidate(pair_age_seconds=1200.0)
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertNotIn("pair_age_seconds", fp)

    def test_activity_bucket_populated_from_derive_activity_bucket(self):
        # High-activity candidate → ACTIVITY_HIGH.
        candidate = _fast_candidate()
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertEqual(fp["activity_bucket"], "ACTIVITY_HIGH")

    def test_source_channel_in_fingerprint(self):
        candidate = _fast_candidate(source_channel="GECKOTERMINAL_NEW_POOL")
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertEqual(fp["source_channel"], "GECKOTERMINAL_NEW_POOL")

    def test_primary_bucket_in_fingerprint(self):
        candidate = _fast_candidate(primary_bucket="B5")
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertEqual(fp["primary_bucket"], "B5")

    def test_pair_age_context_label_in_fingerprint(self):
        candidate = _fast_candidate(pair_age_context_label="RECENT_PAIR_FOR_EXISTING_TOKEN")
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertEqual(fp["pair_age_context_label"], "RECENT_PAIR_FOR_EXISTING_TOKEN")

    def test_missing_fields_produce_none_not_error(self):
        fp = compute_evidence_identity_fingerprint({})
        self.assertIsNone(fp["pair_age_context_label"])
        self.assertIsNone(fp["source_channel"])
        self.assertIsNone(fp["primary_bucket"])

    def test_fingerprint_does_not_mutate_candidate(self):
        candidate = _fast_candidate(token_age_seconds=600.0, pair_age_seconds=1200.0)
        original_tok = candidate["token_age_seconds"]
        original_pair = candidate["pair_age_seconds"]
        compute_evidence_identity_fingerprint(candidate)
        self.assertEqual(candidate["token_age_seconds"], original_tok)
        self.assertEqual(candidate["pair_age_seconds"], original_pair)


# ---------------------------------------------------------------------------
# Fingerprint meaningful-change detection
# ---------------------------------------------------------------------------

class TestFingerprintChangeMeaningful(unittest.TestCase):

    def _base_fp(self, **overrides):
        fp = {
            "activity_bucket": "ACTIVITY_HIGH",
            "pair_age_context_label": None,
            "source_channel": "DEXSCREENER_SEARCH",
            "primary_bucket": "A1",
        }
        fp.update(overrides)
        return fp

    def test_identical_fingerprint_not_meaningful(self):
        fp = self._base_fp()
        self.assertFalse(fingerprint_change_is_meaningful(fp, fp.copy()))

    def test_activity_bucket_change_is_meaningful(self):
        old = self._base_fp(activity_bucket="ACTIVITY_DEAD")
        new = self._base_fp(activity_bucket="ACTIVITY_REVIVING")
        self.assertTrue(fingerprint_change_is_meaningful(old, new))

    def test_source_channel_change_is_meaningful(self):
        old = self._base_fp(source_channel="DEXSCREENER_SEARCH")
        new = self._base_fp(source_channel="GECKOTERMINAL_NEW_POOL")
        self.assertTrue(fingerprint_change_is_meaningful(old, new))

    def test_cross_group_bucket_change_is_meaningful(self):
        # D1 (Group D) → B1 (Group B) with same activity and source.
        old = self._base_fp(activity_bucket="ACTIVITY_MEDIUM", primary_bucket="D1")
        new = self._base_fp(activity_bucket="ACTIVITY_MEDIUM", primary_bucket="B1")
        self.assertTrue(fingerprint_change_is_meaningful(old, new))

    def test_within_group_bucket_change_is_not_meaningful(self):
        # A1 → A2 (both Group A) with same activity and source.
        old = self._base_fp(primary_bucket="A1")
        new = self._base_fp(primary_bucket="A2")
        self.assertFalse(fingerprint_change_is_meaningful(old, new))

    def test_only_pair_age_label_change_is_not_meaningful(self):
        old = self._base_fp(pair_age_context_label="RECENT_PAIR_FOR_EXISTING_TOKEN")
        new = self._base_fp(pair_age_context_label="PAIR_ONLY_AGE_KNOWN")
        self.assertFalse(fingerprint_change_is_meaningful(old, new))

    def test_d_to_c_bucket_cross_group_is_meaningful(self):
        # D3 → C1: Group D → Group C, same activity.
        old = self._base_fp(activity_bucket="ACTIVITY_LOW", primary_bucket="D3")
        new = self._base_fp(activity_bucket="ACTIVITY_LOW", primary_bucket="C1")
        self.assertTrue(fingerprint_change_is_meaningful(old, new))

    def test_b_to_b_within_group_not_meaningful(self):
        old = self._base_fp(activity_bucket="ACTIVITY_MEDIUM", primary_bucket="B1")
        new = self._base_fp(activity_bucket="ACTIVITY_MEDIUM", primary_bucket="B5")
        self.assertFalse(fingerprint_change_is_meaningful(old, new))

    def test_unknown_bucket_group_produces_none_not_error(self):
        # Unknown bucket IDs return None from _bucket_group; None != None is False,
        # so two unknowns with same activity/source are not meaningful.
        old = self._base_fp(primary_bucket="UNKNOWN_BUCKET_X")
        new = self._base_fp(primary_bucket="UNKNOWN_BUCKET_Y")
        # Two different unknown buckets: _bucket_group returns None for both,
        # None == None → same group → not meaningful (activity/source same).
        self.assertFalse(fingerprint_change_is_meaningful(old, new))

    def test_activity_change_overrides_same_bucket(self):
        # Even if bucket and source unchanged, activity change is meaningful.
        old = self._base_fp(activity_bucket="ACTIVITY_LOW", primary_bucket="B5")
        new = self._base_fp(activity_bucket="ACTIVITY_HIGH", primary_bucket="B5")
        self.assertTrue(fingerprint_change_is_meaningful(old, new))


# ---------------------------------------------------------------------------
# Rotation state persistence via record_selection_rotation_state
# ---------------------------------------------------------------------------

class TestRecordSelectionRotationState(unittest.TestCase):

    def test_selected_item_written(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        count = record_selection_rotation_state(conn, [item], "BATCH_001", 1)
        self.assertEqual(count, 1)
        row = conn.execute(
            "SELECT * FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["token_mint"], candidate["token_mint"])
        self.assertEqual(row["pair_address"], candidate["pair_address"])
        self.assertEqual(row["last_selected_batch_id"], "BATCH_001")
        self.assertEqual(row["last_selected_batch_seq"], 1)
        conn.close()

    def test_rejected_item_not_written(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = build_batch_item(
            candidate,
            item_status=ITEM_STATUS_REJECTED,
            rejection_reason="MINT_DUPLICATE",
        )
        count = record_selection_rotation_state(conn, [item], "BATCH_REJ_001", 1)
        self.assertEqual(count, 0)
        row = conn.execute(
            "SELECT * FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertIsNone(row)
        conn.close()

    def test_selection_count_starts_at_1(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        record_selection_rotation_state(conn, [item], "BATCH_001", 1)
        row = conn.execute(
            "SELECT selection_count FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertEqual(row["selection_count"], 1)
        conn.close()

    def test_selection_count_increments_on_reselection(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        record_selection_rotation_state(conn, [item], "BATCH_001", 1)
        record_selection_rotation_state(conn, [item], "BATCH_002", 2)
        row = conn.execute(
            "SELECT selection_count FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertEqual(row["selection_count"], 2)
        conn.close()

    def test_last_batch_id_updated_on_reselection(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        record_selection_rotation_state(conn, [item], "BATCH_001", 1)
        record_selection_rotation_state(conn, [item], "BATCH_002", 2)
        row = conn.execute(
            "SELECT last_selected_batch_id FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertEqual(row["last_selected_batch_id"], "BATCH_002")
        conn.close()

    def test_evidence_fingerprint_json_stored_and_valid(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        record_selection_rotation_state(conn, [item], "BATCH_FP_001", 1)
        row = conn.execute(
            "SELECT last_evidence_fingerprint_json FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertIsNotNone(row["last_evidence_fingerprint_json"])
        fp = json.loads(row["last_evidence_fingerprint_json"])
        self.assertIn("activity_bucket", fp)
        self.assertIn("primary_bucket", fp)
        self.assertIn("source_channel", fp)
        self.assertIn("pair_age_context_label", fp)
        self.assertEqual(len(fp), 4)
        conn.close()

    def test_item_without_mint_skipped(self):
        conn = _make_db()
        item = {"item_status": ITEM_STATUS_SELECTED, "token_mint": "", "pair_address": "PAIR_A"}
        count = record_selection_rotation_state(conn, [item], "BATCH_SKIP_001", 1)
        self.assertEqual(count, 0)
        conn.close()

    def test_item_without_pair_address_skipped(self):
        conn = _make_db()
        item = {"item_status": ITEM_STATUS_SELECTED, "token_mint": "MINT_A", "pair_address": ""}
        count = record_selection_rotation_state(conn, [item], "BATCH_SKIP_002", 1)
        self.assertEqual(count, 0)
        conn.close()

    def test_returns_zero_for_empty_items(self):
        conn = _make_db()
        count = record_selection_rotation_state(conn, [], "BATCH_EMPTY", 1)
        self.assertEqual(count, 0)
        conn.close()

    def test_multiple_selected_items_all_written(self):
        conn = _make_db()
        candidate_a = _fast_candidate(
            token_mint="MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            pair_address="PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        candidate_b = _fast_candidate(
            token_mint="MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            pair_address="PairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        items = [_make_selected_item(candidate_a), _make_selected_item(candidate_b)]
        count = record_selection_rotation_state(conn, items, "BATCH_MULTI", 5)
        self.assertEqual(count, 2)
        rows = conn.execute(
            "SELECT token_mint FROM printer_selection_rotation_state ORDER BY token_mint"
        ).fetchall()
        mints = [r["token_mint"] for r in rows]
        self.assertIn(candidate_a["token_mint"], mints)
        self.assertIn(candidate_b["token_mint"], mints)
        conn.close()


# ---------------------------------------------------------------------------
# Rotation state persistence via persist_selection_batch (wiring test)
# ---------------------------------------------------------------------------

class TestPersistSelectionBatchRotationStateWiring(unittest.TestCase):

    def test_persist_writes_rotation_state_for_selected(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        result = persist_selection_batch(conn, "RSS_WIRE_001", [item])
        self.assertTrue(result.get("rotation_state_recorded"))
        row = conn.execute(
            "SELECT * FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row["last_selected_batch_id"], "RSS_WIRE_001")
        conn.close()

    def test_persist_rotation_state_recorded_field_in_return(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        result = persist_selection_batch(conn, "RSS_FIELD_001", [item])
        self.assertIn("rotation_state_recorded", result)
        self.assertIsInstance(result["rotation_state_recorded"], bool)
        conn.close()

    def test_persist_does_not_write_rotation_state_for_rejected(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = build_batch_item(
            candidate,
            item_status=ITEM_STATUS_REJECTED,
            rejection_reason="MINT_DUPLICATE",
        )
        persist_selection_batch(conn, "RSS_REJ_WIRE_001", [item])
        row = conn.execute(
            "SELECT * FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertIsNone(row)
        conn.close()

    def test_persist_twice_increments_selection_count(self):
        conn = _make_db()
        candidate = _fast_candidate()

        def _item():
            return _make_selected_item(candidate)

        persist_selection_batch(conn, "RSS_INC_001", [_item()])
        persist_selection_batch(conn, "RSS_INC_002", [_item()])
        row = conn.execute(
            "SELECT selection_count FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        self.assertEqual(row["selection_count"], 2)
        conn.close()

    def test_batch_seq_increases_across_persists(self):
        conn = _make_db()
        candidate_a = _fast_candidate(
            token_mint="MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            pair_address="PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        candidate_b = _fast_candidate(
            token_mint="MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            pair_address="PairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        persist_selection_batch(conn, "SEQ_BATCH_001", [_make_selected_item(candidate_a)])
        persist_selection_batch(conn, "SEQ_BATCH_002", [_make_selected_item(candidate_b)])
        rows = conn.execute(
            "SELECT token_mint, last_selected_batch_seq FROM printer_selection_rotation_state "
            "ORDER BY last_selected_batch_seq"
        ).fetchall()
        self.assertEqual(len(rows), 2)
        seqs = [r["last_selected_batch_seq"] for r in rows]
        self.assertGreater(seqs[1], seqs[0])
        conn.close()

    def test_cooldown_check_blocked_after_persist(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        persist_selection_batch(conn, "COOLDOWN_TEST_001", [item])
        # Retrieve the batch seq that was assigned.
        row = conn.execute(
            "SELECT last_selected_batch_seq FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        seq = row["last_selected_batch_seq"]
        # Next batch seq (seq+1) should be blocked.
        ok, reason = check_token_selection_cooldown(
            conn, candidate["token_mint"], current_batch_seq=seq + 1
        )
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_cooldown_check_allowed_after_full_window(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        persist_selection_batch(conn, "COOLDOWN_ALLOW_001", [item])
        row = conn.execute(
            "SELECT last_selected_batch_seq FROM printer_selection_rotation_state WHERE token_mint = ?",
            (candidate["token_mint"],),
        ).fetchone()
        seq = row["last_selected_batch_seq"]
        # seq + 3 allows (batches_since=3, not <3).
        ok, reason = check_token_selection_cooldown(
            conn, candidate["token_mint"], current_batch_seq=seq + 3
        )
        self.assertTrue(ok)
        self.assertEqual(reason, "")
        conn.close()


# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------

class TestRotationStateSafety(unittest.TestCase):

    def test_rejection_constants_are_strings(self):
        self.assertIsInstance(REJECTION_TOKEN_SELECTION_COOLDOWN, str)
        self.assertIsInstance(REJECTION_PAIR_SELECTION_COOLDOWN, str)

    def test_rejection_constants_distinct(self):
        self.assertNotEqual(REJECTION_TOKEN_SELECTION_COOLDOWN, REJECTION_PAIR_SELECTION_COOLDOWN)

    def test_fingerprint_does_not_include_numeric_score(self):
        candidate = _fast_candidate()
        fp = compute_evidence_identity_fingerprint(candidate)
        for val in fp.values():
            self.assertNotIsInstance(val, (int, float), f"Numeric found in fingerprint: {val!r}")

    def test_persist_does_not_write_paper_decisions(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        persist_selection_batch(conn, "SAFE_001", [item])
        count = conn.execute("SELECT COUNT(*) FROM printer_paper_decisions").fetchone()[0]
        self.assertEqual(count, 0)
        conn.close()

    def test_token_age_not_modified_by_fingerprint(self):
        candidate = _fast_candidate(token_age_seconds=600.0, pair_age_seconds=1200.0)
        original_tok = candidate["token_age_seconds"]
        original_pair = candidate["pair_age_seconds"]
        compute_evidence_identity_fingerprint(candidate)
        self.assertEqual(candidate["token_age_seconds"], original_tok)
        self.assertEqual(candidate["pair_age_seconds"], original_pair)

    def test_pair_age_not_written_to_token_age_seconds(self):
        # pair_age_seconds must never appear as token_age_seconds in the fingerprint.
        candidate = _fast_candidate(
            token_age_seconds=None,
            pair_age_seconds=1200.0,
        )
        fp = compute_evidence_identity_fingerprint(candidate)
        self.assertNotIn("token_age_seconds", fp)
        self.assertNotIn("pair_age_seconds", fp)
        # activity_bucket for a None-liquidity-candidate is ACTIVITY_UNKNOWN.
        # But primary_bucket=None. No pair age leaks as token age.
        self.assertNotEqual(fp.get("activity_bucket"), 1200.0)

    def test_fingerprint_fields_are_only_categorical(self):
        candidate = _fast_candidate(
            liquidity_usd=10000.0,
            volume_5m=2000.0,
            primary_bucket="A1",
            source_channel="DEXSCREENER_SEARCH",
        )
        fp = compute_evidence_identity_fingerprint(candidate)
        for key, val in fp.items():
            if val is not None:
                self.assertIsInstance(
                    val, str, f"Non-string, non-None value in fingerprint[{key!r}]: {val!r}"
                )

    def test_record_rotation_state_does_not_affect_token_tracking_tables(self):
        conn = _make_db()
        candidate = _fast_candidate()
        item = _make_selected_item(candidate)
        record_selection_rotation_state(conn, [item], "SAFE_TRACK_001", 1)
        count = conn.execute(
            "SELECT COUNT(*) FROM printer_tokens"
        ).fetchone()[0]
        self.assertEqual(count, 0)
        conn.close()

    def test_rotation_state_table_separate_from_token_tables(self):
        # Ensure the rotation state table is the correct one and not clobbering others.
        conn = _make_db()
        tables = {
            row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        self.assertIn("printer_selection_rotation_state", tables)
        self.assertIn("printer_tokens", tables)
        self.assertIn("printer_pairs", tables)
        conn.close()


# ---------------------------------------------------------------------------
# V2-2S.2: Multi-pair token cooldown safety (latest-row fix)
# ---------------------------------------------------------------------------

class TestMultiPairTokenCooldownLatestRow(unittest.TestCase):
    """Token cooldown must use the latest selected batch seq across all pair rows.

    A mint with two pair rows (old pair at seq 1, new pair at seq 5) must be
    blocked based on seq 5, not seq 1. Without MAX() the old query could return
    the seq-1 row and evaluate batches_since=4 as allowed when window=3, even
    though the mint was actually re-selected at seq 5.
    """

    def test_latest_pair_row_controls_token_cooldown(self):
        conn = _make_db()
        # MINT_A on PAIR_A selected at seq 1 (old).
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        # MINT_A on PAIR_B selected at seq 5 (newer pair, newer batch).
        _seed_rotation_state(conn, "MINT_A", "PAIR_B", batch_seq=5)
        # At seq 6, batches_since from seq 5 = 1, which is < 3 → must be BLOCKED.
        ok, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=6)
        self.assertFalse(ok, "Token cooldown must use the latest batch seq (5), not the old one (1)")
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_old_pair_row_does_not_allow_too_early(self):
        conn = _make_db()
        # MINT_A on PAIR_A at seq 1 — if only this row existed, seq 4 would be allowed.
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        # MINT_A on PAIR_B at seq 4 — now the latest is 4, seq 6 is batches_since=2 → blocked.
        _seed_rotation_state(conn, "MINT_A", "PAIR_B", batch_seq=4)
        ok, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=6)
        self.assertFalse(ok, "Latest seq (4) must control; batches_since=2 < 3 → blocked")
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_allowed_only_when_latest_seq_clears_window(self):
        conn = _make_db()
        # MINT_A on PAIR_A at seq 1.
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        # MINT_A on PAIR_B at seq 5.
        _seed_rotation_state(conn, "MINT_A", "PAIR_B", batch_seq=5)
        # seq 8: batches_since from 5 = 3, 3 < 3 is False → allowed.
        ok, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=8)
        self.assertTrue(ok, "batches_since=3 clears window=3; must be allowed")
        self.assertEqual(reason, "")
        conn.close()

    def test_single_pair_row_still_works(self):
        conn = _make_db()
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=3)
        ok, reason = check_token_selection_cooldown(conn, "MINT_A", current_batch_seq=5)
        self.assertFalse(ok)
        self.assertEqual(reason, REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_pair_cooldown_still_pair_specific_with_multi_rows(self):
        conn = _make_db()
        # MINT_A on PAIR_A at seq 1 (old), MINT_A on PAIR_B at seq 5 (new).
        _seed_rotation_state(conn, "MINT_A", "PAIR_A", batch_seq=1)
        _seed_rotation_state(conn, "MINT_A", "PAIR_B", batch_seq=5)
        # PAIR_A: batches_since from seq 1 at current seq 4 = 3, allowed (3 < 3 is False).
        ok_a, _ = check_pair_selection_cooldown(conn, "PAIR_A", current_batch_seq=4)
        self.assertTrue(ok_a, "PAIR_A cleared its window; pair cooldown must be pair-specific")
        # PAIR_B: batches_since from seq 5 at current seq 6 = 1, still blocked.
        ok_b, reason_b = check_pair_selection_cooldown(conn, "PAIR_B", current_batch_seq=6)
        self.assertFalse(ok_b, "PAIR_B in cooldown; pair check must be independent per pair")
        self.assertEqual(reason_b, REJECTION_PAIR_SELECTION_COOLDOWN)
        conn.close()


# ---------------------------------------------------------------------------
# V2-2S.2: apply_selection_cooldown_gates wiring helper
# ---------------------------------------------------------------------------

class TestApplySelectionCooldownGates(unittest.TestCase):
    """Integration tests for the apply_selection_cooldown_gates wiring helper.

    Verifies that candidates are filtered before batch acceptance, that
    rejected candidates carry the correct categorical rejection reason, and
    that eligible candidates pass through unmodified.
    """

    def test_no_prior_state_all_eligible(self):
        conn = _make_db()
        candidates = [
            _fast_candidate(
                token_mint="MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
                pair_address="PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
            ),
            _fast_candidate(
                token_mint="MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
                pair_address="PairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            ),
        ]
        eligible, rejected = apply_selection_cooldown_gates(conn, candidates, current_batch_seq=1)
        self.assertEqual(len(eligible), 2)
        self.assertEqual(len(rejected), 0)
        conn.close()

    def test_token_cooldown_rejects_candidate(self):
        conn = _make_db()
        mint = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        pair = "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        _seed_rotation_state(conn, mint, pair, batch_seq=1)
        candidate = _fast_candidate(token_mint=mint, pair_address=pair)
        eligible, rejected = apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=2)
        self.assertEqual(len(eligible), 0)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["rejection_reason"], REJECTION_TOKEN_SELECTION_COOLDOWN)
        self.assertEqual(rejected[0]["item_status"], "REJECTED")
        conn.close()

    def test_pair_cooldown_rejects_candidate(self):
        conn = _make_db()
        # Seed MINT_A on PAIR_A but check MINT_B on PAIR_A (different mint, same pair).
        _seed_rotation_state(conn, "MINT_SEED", "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", batch_seq=1)
        # MINT_B has no token cooldown, but PAIR_A has pair cooldown.
        candidate = _fast_candidate(
            token_mint="MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
            pair_address="PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
        )
        eligible, rejected = apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=2)
        self.assertEqual(len(eligible), 0)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["rejection_reason"], REJECTION_PAIR_SELECTION_COOLDOWN)
        conn.close()

    def test_token_cooldown_checked_before_pair(self):
        conn = _make_db()
        mint = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        pair = "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        _seed_rotation_state(conn, mint, pair, batch_seq=1)
        # Both token and pair are in cooldown; token is checked first.
        candidate = _fast_candidate(token_mint=mint, pair_address=pair)
        eligible, rejected = apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=2)
        self.assertEqual(len(rejected), 1)
        # Token check fires first → TOKEN_SELECTION_COOLDOWN.
        self.assertEqual(rejected[0]["rejection_reason"], REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()

    def test_candidate_passes_after_cooldown_window(self):
        conn = _make_db()
        mint = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        pair = "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        _seed_rotation_state(conn, mint, pair, batch_seq=1)
        candidate = _fast_candidate(token_mint=mint, pair_address=pair)
        # seq 4: batches_since = 3, 3 < 3 is False → eligible.
        eligible, rejected = apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=4)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(len(rejected), 0)
        conn.close()

    def test_rejected_candidate_has_correct_item_status(self):
        conn = _make_db()
        mint = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        pair = "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        _seed_rotation_state(conn, mint, pair, batch_seq=1)
        candidate = _fast_candidate(token_mint=mint, pair_address=pair)
        _, rejected = apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=2)
        self.assertEqual(rejected[0]["item_status"], ITEM_STATUS_REJECTED)
        conn.close()

    def test_eligible_candidate_unmodified(self):
        conn = _make_db()
        candidate = _fast_candidate()
        eligible, _ = apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=1)
        self.assertEqual(len(eligible), 1)
        # No extra keys injected.
        self.assertNotIn("item_status", eligible[0])
        self.assertNotIn("rejection_reason", eligible[0])
        conn.close()

    def test_mixed_batch_splits_correctly(self):
        conn = _make_db()
        mint_a = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        pair_a = "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        mint_b = "MintBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        pair_b = "PairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB"
        _seed_rotation_state(conn, mint_a, pair_a, batch_seq=1)
        candidates = [
            _fast_candidate(token_mint=mint_a, pair_address=pair_a),  # in cooldown
            _fast_candidate(token_mint=mint_b, pair_address=pair_b),  # fresh
        ]
        eligible, rejected = apply_selection_cooldown_gates(conn, candidates, current_batch_seq=2)
        self.assertEqual(len(eligible), 1)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(eligible[0]["token_mint"], mint_b)
        self.assertEqual(rejected[0]["token_mint"], mint_a)
        conn.close()

    def test_empty_candidates_returns_empty_lists(self):
        conn = _make_db()
        eligible, rejected = apply_selection_cooldown_gates(conn, [], current_batch_seq=1)
        self.assertEqual(eligible, [])
        self.assertEqual(rejected, [])
        conn.close()

    def test_rejected_cooldown_candidate_does_not_enter_selected_items(self):
        # Simulate a gated batch: apply gates, then persist only the eligible portion.
        conn = _make_db()
        mint = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        pair = "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        _seed_rotation_state(conn, mint, pair, batch_seq=1)
        candidates = [_fast_candidate(token_mint=mint, pair_address=pair)]
        eligible, rejected_candidates = apply_selection_cooldown_gates(
            conn, candidates, current_batch_seq=2
        )
        # Build items only from eligible (none in this case).
        selected_items = [_make_selected_item(c) for c in eligible]
        rejected_items = [
            build_batch_item(c, item_status=ITEM_STATUS_REJECTED,
                             rejection_reason=c.get("rejection_reason"))
            for c in rejected_candidates
        ]
        all_items = selected_items + rejected_items
        result = persist_selection_batch(conn, "GATE_TEST_001", all_items)
        self.assertEqual(result["selected_count"], 0)
        self.assertEqual(result["rejected_count"], 1)
        # Rotation state must NOT have been updated for the rejected mint.
        row = conn.execute(
            "SELECT last_selected_batch_id FROM printer_selection_rotation_state WHERE token_mint = ?",
            (mint,),
        ).fetchone()
        # Row exists from the seed but batch_id must still be "SEED_BATCH" (not updated).
        self.assertEqual(row["last_selected_batch_id"], "SEED_BATCH")
        conn.close()

    def test_no_paper_decisions_created(self):
        conn = _make_db()
        candidate = _fast_candidate()
        apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=1)
        count = conn.execute("SELECT COUNT(*) FROM printer_paper_decisions").fetchone()[0]
        self.assertEqual(count, 0)
        conn.close()

    def test_no_token_tracking_rows_created(self):
        conn = _make_db()
        candidate = _fast_candidate()
        apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=1)
        count = conn.execute("SELECT COUNT(*) FROM printer_tokens").fetchone()[0]
        self.assertEqual(count, 0)
        conn.close()

    def test_returns_tuple_of_two_lists(self):
        conn = _make_db()
        result = apply_selection_cooldown_gates(conn, [], current_batch_seq=1)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        self.assertIsInstance(result[0], list)
        self.assertIsInstance(result[1], list)
        conn.close()

    def test_new_pair_for_same_mint_blocked_by_token_cooldown(self):
        conn = _make_db()
        mint = "MintAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        # Seed: mint on PAIR_A selected at seq 1.
        _seed_rotation_state(conn, mint, "PairAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", batch_seq=1)
        # Now try the same mint on a NEW pair_b at seq 2.
        candidate = _fast_candidate(
            token_mint=mint,
            pair_address="PairBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBBB",
        )
        eligible, rejected = apply_selection_cooldown_gates(conn, [candidate], current_batch_seq=2)
        self.assertEqual(len(eligible), 0)
        self.assertEqual(len(rejected), 1)
        self.assertEqual(rejected[0]["rejection_reason"], REJECTION_TOKEN_SELECTION_COOLDOWN)
        conn.close()


if __name__ == "__main__":
    unittest.main()
