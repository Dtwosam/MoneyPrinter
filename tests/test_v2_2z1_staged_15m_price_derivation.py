"""V2-2Z.1 / V2-2Z.2 — Staged Price-Change 15m Derivation.

Tests covering:
  A. Pure derive_price_change_15m: eligibility, formula, rejection rules (32 cases)
  B. find_eligible_snapshot_pairs: DB query, interval selection, tie-break
  C. apply_staged_derivation: integration with recorder.record_token_snapshot
  D. Safety: volume_15m / txns_15m remain None; no memory / retrieval / paper rows

No live source calls, no memory generation, no retrieval, no paper decisions,
no BUY/SELL/HOLD, no positions/trades/audits/PnL, no scoring/ranking/confidence/
weighted logic, no migrations, no mutation of persistent DB.
"""

from __future__ import annotations

import json
import pathlib
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db import apply_migrations
from printer_v1.snapshots.staged_derivation import (
    DERIVATION_KIND_STAGED_SNAPSHOT_PRICE_CHANGE_15M,
    StagedDerivationResult,
    apply_staged_derivation,
    derive_price_change_15m,
    find_eligible_snapshot_pairs,
)
from printer_v1.snapshots.recorder import record_token_snapshot


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 7, 9, 12, 0, 0, tzinfo=timezone.utc)
_NOW_ISO = _NOW.isoformat()
_START_ISO = (_NOW - timedelta(seconds=900)).isoformat()   # exact 15m ago
_START_720 = (_NOW - timedelta(seconds=720)).isoformat()   # lower boundary
_START_1080 = (_NOW - timedelta(seconds=1080)).isoformat() # upper boundary
_START_719 = (_NOW - timedelta(seconds=719)).isoformat()   # below lower boundary
_START_1081 = (_NOW - timedelta(seconds=1081)).isoformat() # above upper boundary


def _snap(**overrides) -> dict:
    """Minimal valid snapshot dict for pure-function tests."""
    base: dict = {
        "id": 1,
        "token_id": 10,
        "pair_id": 20,
        "source_name": "dexscreener",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "snapshot_quality_label": "PARTIAL_SNAPSHOT",
        "price_usd": 0.010,
        "captured_at": _START_ISO,
        "volume_15m": None,
        "txns_15m": None,
    }
    base.update(overrides)
    return base


def _end_snap(**overrides) -> dict:
    """Minimal valid end snapshot dict for pure-function tests."""
    base: dict = {
        "id": 2,
        "token_id": 10,
        "pair_id": 20,
        "source_name": "dexscreener",
        "source_status": "COMPLETE",
        "data_quality_label": "CLEAN_DATA",
        "snapshot_quality_label": "PARTIAL_SNAPSHOT",
        "price_usd": 0.015,
        "captured_at": _NOW_ISO,
        "volume_15m": None,
        "txns_15m": None,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# A. Pure derive_price_change_15m tests
# ---------------------------------------------------------------------------

class TestDerivePrice15mPure(unittest.TestCase):

    # --- Valid derivation ---

    def test_valid_900s_interval_produces_result(self):
        result = derive_price_change_15m(_snap(), _end_snap())
        self.assertIsNotNone(result)
        self.assertIsInstance(result, StagedDerivationResult)

    def test_formula_positive_price_change(self):
        # 0.010 → 0.015 = +50%
        result = derive_price_change_15m(_snap(price_usd=0.010), _end_snap(price_usd=0.015))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.derived_price_change_15m, 50.0, places=4)

    def test_formula_negative_price_change(self):
        # 0.020 → 0.010 = -50%
        result = derive_price_change_15m(_snap(price_usd=0.020), _end_snap(price_usd=0.010))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.derived_price_change_15m, -50.0, places=4)

    def test_formula_zero_price_change(self):
        result = derive_price_change_15m(_snap(price_usd=0.010), _end_snap(price_usd=0.010))
        self.assertIsNotNone(result)
        self.assertEqual(result.derived_price_change_15m, 0.0)

    def test_formula_precision_6_decimal_places(self):
        # 0.010 → 0.010333... gives a non-trivial decimal
        result = derive_price_change_15m(_snap(price_usd=3.0), _end_snap(price_usd=4.0))
        self.assertIsNotNone(result)
        # ((4-3)/3)*100 = 33.333333...
        self.assertEqual(result.derived_price_change_15m, round(100 / 3, 6))

    # --- Tolerance boundary tests ---

    def test_lower_tolerance_boundary_accepted(self):
        result = derive_price_change_15m(
            _snap(captured_at=_START_720),
            _end_snap(),
        )
        self.assertIsNotNone(result)

    def test_upper_tolerance_boundary_accepted(self):
        result = derive_price_change_15m(
            _snap(captured_at=_START_1080),
            _end_snap(),
        )
        self.assertIsNotNone(result)

    def test_below_lower_tolerance_rejected(self):
        result = derive_price_change_15m(
            _snap(captured_at=_START_719),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_above_upper_tolerance_rejected(self):
        result = derive_price_change_15m(
            _snap(captured_at=_START_1081),
            _end_snap(),
        )
        self.assertIsNone(result)

    # --- Identity rejection tests ---

    def test_token_id_mismatch_rejected(self):
        result = derive_price_change_15m(_snap(token_id=10), _end_snap(token_id=99))
        self.assertIsNone(result)

    def test_pair_id_mismatch_rejected(self):
        result = derive_price_change_15m(_snap(pair_id=20), _end_snap(pair_id=88))
        self.assertIsNone(result)

    def test_source_name_mismatch_rejected(self):
        result = derive_price_change_15m(
            _snap(source_name="dexscreener"),
            _end_snap(source_name="geckoterminal"),
        )
        self.assertIsNone(result)

    def test_null_pair_id_start_rejected(self):
        result = derive_price_change_15m(_snap(pair_id=None), _end_snap())
        self.assertIsNone(result)

    def test_null_pair_id_end_rejected(self):
        result = derive_price_change_15m(_snap(), _end_snap(pair_id=None))
        self.assertIsNone(result)

    def test_null_token_id_start_rejected(self):
        result = derive_price_change_15m(_snap(token_id=None), _end_snap())
        self.assertIsNone(result)

    def test_null_token_id_end_rejected(self):
        result = derive_price_change_15m(_snap(), _end_snap(token_id=None))
        self.assertIsNone(result)

    # --- Quality rejection tests ---

    def test_dirty_data_label_rejected(self):
        result = derive_price_change_15m(
            _snap(data_quality_label="DIRTY_DATA"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_stale_data_label_rejected(self):
        result = derive_price_change_15m(
            _snap(data_quality_label="STALE_DATA"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_acceptable_partial_data_label_rejected(self):
        # Only CLEAN_DATA is allowed; ACCEPTABLE_PARTIAL_DATA is not sufficient
        result = derive_price_change_15m(
            _snap(data_quality_label="ACCEPTABLE_PARTIAL_DATA"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_failed_source_status_rejected(self):
        result = derive_price_change_15m(
            _snap(source_status="FAILED"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_partial_source_status_rejected(self):
        result = derive_price_change_15m(
            _snap(source_status="PARTIAL"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_dirty_snapshot_quality_label_rejected(self):
        result = derive_price_change_15m(
            _snap(snapshot_quality_label="DIRTY_SNAPSHOT"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_stale_snapshot_quality_label_rejected(self):
        result = derive_price_change_15m(
            _snap(snapshot_quality_label="STALE_SNAPSHOT"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_missing_critical_fields_snapshot_quality_label_rejected(self):
        result = derive_price_change_15m(
            _snap(snapshot_quality_label="MISSING_CRITICAL_FIELDS"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_conflicting_snapshot_quality_label_rejected(self):
        result = derive_price_change_15m(
            _snap(snapshot_quality_label="CONFLICTING_SNAPSHOT"),
            _end_snap(),
        )
        self.assertIsNone(result)

    def test_partial_snapshot_quality_label_allowed(self):
        # PARTIAL_SNAPSHOT is the expected label for all current live snapshots
        result = derive_price_change_15m(
            _snap(snapshot_quality_label="PARTIAL_SNAPSHOT"),
            _end_snap(snapshot_quality_label="PARTIAL_SNAPSHOT"),
        )
        self.assertIsNotNone(result)

    # --- Price rejection tests ---

    def test_null_start_price_rejected(self):
        result = derive_price_change_15m(_snap(price_usd=None), _end_snap())
        self.assertIsNone(result)

    def test_null_end_price_rejected(self):
        result = derive_price_change_15m(_snap(), _end_snap(price_usd=None))
        self.assertIsNone(result)

    def test_zero_start_price_rejected(self):
        result = derive_price_change_15m(_snap(price_usd=0), _end_snap())
        self.assertIsNone(result)

    def test_negative_start_price_rejected(self):
        result = derive_price_change_15m(_snap(price_usd=-0.001), _end_snap())
        self.assertIsNone(result)

    # --- Timestamp rejection tests ---

    def test_end_before_start_rejected(self):
        result = derive_price_change_15m(
            _snap(captured_at=_NOW_ISO),
            _end_snap(captured_at=_START_ISO),
        )
        self.assertIsNone(result)

    def test_equal_timestamps_rejected(self):
        result = derive_price_change_15m(
            _snap(captured_at=_NOW_ISO),
            _end_snap(captured_at=_NOW_ISO),
        )
        self.assertIsNone(result)

    def test_null_start_captured_at_rejected(self):
        result = derive_price_change_15m(_snap(captured_at=None), _end_snap())
        self.assertIsNone(result)

    def test_null_end_captured_at_rejected(self):
        result = derive_price_change_15m(_snap(), _end_snap(captured_at=None))
        self.assertIsNone(result)

    # --- Extreme value tests ---

    def test_extreme_positive_change_accepted(self):
        # +2000% — valid for memecoins
        result = derive_price_change_15m(_snap(price_usd=0.001), _end_snap(price_usd=0.021))
        self.assertIsNotNone(result)
        self.assertGreater(result.derived_price_change_15m, 1000.0)

    def test_extreme_negative_change_accepted(self):
        # -98% — valid for memecoins
        result = derive_price_change_15m(_snap(price_usd=100.0), _end_snap(price_usd=2.0))
        self.assertIsNotNone(result)
        self.assertLess(result.derived_price_change_15m, -90.0)

    # --- Provenance tests ---

    def test_provenance_all_17_fields_present(self):
        result = derive_price_change_15m(_snap(), _end_snap())
        self.assertIsNotNone(result)
        p = result.provenance
        expected_keys = {
            "derivation_kind",
            "start_snapshot_id",
            "end_snapshot_id",
            "token_id",
            "pair_id",
            "source_name",
            "start_captured_at",
            "end_captured_at",
            "interval_seconds",
            "start_price_usd",
            "end_price_usd",
            "derived_price_change_15m",
            "start_data_quality_label",
            "end_data_quality_label",
            "start_source_status",
            "end_source_status",
            "derived_at",
        }
        self.assertEqual(set(p.keys()), expected_keys)

    def test_provenance_derivation_kind_constant(self):
        result = derive_price_change_15m(_snap(), _end_snap())
        self.assertIsNotNone(result)
        self.assertEqual(
            result.provenance["derivation_kind"],
            DERIVATION_KIND_STAGED_SNAPSHOT_PRICE_CHANGE_15M,
        )

    def test_provenance_interval_seconds_correct(self):
        result = derive_price_change_15m(_snap(), _end_snap())
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.provenance["interval_seconds"], 900.0, delta=1.0)

    def test_provenance_prices_preserved(self):
        result = derive_price_change_15m(_snap(price_usd=0.010), _end_snap(price_usd=0.015))
        self.assertIsNotNone(result)
        self.assertAlmostEqual(result.provenance["start_price_usd"], 0.010)
        self.assertAlmostEqual(result.provenance["end_price_usd"], 0.015)

    # --- 15m field hard-block tests (pure function level) ---

    def test_volume_15m_not_set_by_derivation(self):
        # derive_price_change_15m does not touch volume_15m
        start = _snap(volume_15m=None)
        end = _end_snap(volume_15m=None)
        result = derive_price_change_15m(start, end)
        self.assertIsNotNone(result)
        # The result only has derived_price_change_15m and provenance
        self.assertNotIn("volume_15m", result.provenance)

    def test_txns_15m_not_set_by_derivation(self):
        start = _snap(txns_15m=None)
        end = _end_snap(txns_15m=None)
        result = derive_price_change_15m(start, end)
        self.assertIsNotNone(result)
        self.assertNotIn("txns_15m", result.provenance)


# ---------------------------------------------------------------------------
# B. find_eligible_snapshot_pairs tests (requires DB)
# ---------------------------------------------------------------------------

class TestFindEligiblePairs(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "test.sqlite3"
        apply_migrations(self.db_path)
        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = OFF")
        self.token_id = 100
        self.pair_id = 200

    def tearDown(self):
        self.conn.close()
        self.tempdir.cleanup()

    def _insert_snapshot(
        self,
        *,
        captured_at: str,
        price_usd: float = 0.010,
        source_status: str = "COMPLETE",
        data_quality_label: str = "CLEAN_DATA",
        source_name: str = "dexscreener",
        snapshot_quality_label: str = "PARTIAL_SNAPSHOT",
    ) -> int:
        """Insert a minimal snapshot row directly and return its id."""
        payload = {
            "token_id": self.token_id,
            "pair_id": self.pair_id,
            "source_name": source_name,
            "captured_at": captured_at,
            "price_usd": price_usd,
        }
        normalized_json = json.dumps(payload, sort_keys=True)
        cursor = self.conn.execute(
            """
            INSERT INTO printer_token_snapshots (
                token_id, pair_id, captured_at,
                tracking_lane, snapshot_mode,
                price_usd, liquidity_usd,
                source_status, data_quality_label,
                snapshot_quality_label,
                normalized_snapshot_payload_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                self.token_id, self.pair_id, captured_at,
                "TRACK_FAST", "NORMAL_MODE",
                price_usd, 10000.0,
                source_status, data_quality_label,
                snapshot_quality_label,
                normalized_json,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def test_returns_empty_when_no_candidates(self):
        end_snap = {"captured_at": _NOW_ISO}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(rows, [])

    def test_returns_eligible_candidate_at_900s(self):
        self._insert_snapshot(captured_at=_START_ISO)
        end_snap = {"captured_at": _NOW_ISO, "token_id": self.token_id, "pair_id": self.pair_id}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(len(rows), 1)

    def test_excludes_candidate_outside_tolerance(self):
        self._insert_snapshot(captured_at=_START_1081)  # 1081s before → outside
        end_snap = {"captured_at": _NOW_ISO}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(rows, [])

    def test_excludes_dirty_data_candidate(self):
        self._insert_snapshot(
            captured_at=_START_ISO,
            data_quality_label="DIRTY_DATA",
        )
        end_snap = {"captured_at": _NOW_ISO}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(rows, [])

    def test_excludes_failed_source_status_candidate(self):
        self._insert_snapshot(
            captured_at=_START_ISO,
            source_status="FAILED",
        )
        end_snap = {"captured_at": _NOW_ISO}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(rows, [])

    def test_excludes_wrong_source_name(self):
        self._insert_snapshot(captured_at=_START_ISO, source_name="geckoterminal")
        end_snap = {"captured_at": _NOW_ISO}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(rows, [])

    def test_closest_eligible_pair_selected_first(self):
        # Insert three start snapshots at different intervals
        t_730 = (_NOW - timedelta(seconds=730)).isoformat()  # |730-900|=170
        t_850 = (_NOW - timedelta(seconds=850)).isoformat()  # |850-900|=50 ← closest
        t_1050 = (_NOW - timedelta(seconds=1050)).isoformat()  # |1050-900|=150
        self._insert_snapshot(captured_at=t_730)
        self._insert_snapshot(captured_at=t_850)
        self._insert_snapshot(captured_at=t_1050)
        end_snap = {"captured_at": _NOW_ISO}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(len(rows), 3)
        # First row must be the 850s candidate
        from printer_v1.snapshots.quality import parse_timestamp
        first_ts = parse_timestamp(rows[0]["captured_at"])
        expected_ts = parse_timestamp(t_850)
        self.assertEqual(first_ts, expected_ts)

    def test_tie_break_prefers_later_captured_at(self):
        # Two candidates equidistant from 900s (720s and 1080s)
        t_720 = (_NOW - timedelta(seconds=720)).isoformat()  # |720-900|=180, later
        t_1080 = (_NOW - timedelta(seconds=1080)).isoformat()  # |1080-900|=180, earlier
        self._insert_snapshot(captured_at=t_720)
        self._insert_snapshot(captured_at=t_1080)
        end_snap = {"captured_at": _NOW_ISO}
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", end_snap
        )
        self.assertEqual(len(rows), 2)
        # t_720 is later (more recent), so should come first in tie
        from printer_v1.snapshots.quality import parse_timestamp
        first_ts = parse_timestamp(rows[0]["captured_at"])
        expected_ts = parse_timestamp(t_720)
        self.assertEqual(first_ts, expected_ts)

    def test_returns_empty_when_end_captured_at_is_none(self):
        rows = find_eligible_snapshot_pairs(
            self.conn, self.token_id, self.pair_id, "dexscreener", {"captured_at": None}
        )
        self.assertEqual(rows, [])


# ---------------------------------------------------------------------------
# C. apply_staged_derivation and recorder integration tests (requires DB)
# ---------------------------------------------------------------------------

class TestApplyStagedDerivation(unittest.TestCase):

    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = pathlib.Path(self.tempdir.name) / "test.sqlite3"
        apply_migrations(self.db_path)
        self.now = _NOW

    def tearDown(self):
        self.tempdir.cleanup()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _insert_token_pair(self) -> tuple[int, int]:
        conn = self._connect()
        try:
            tid = conn.execute(
                "INSERT INTO printer_tokens (token_mint, chain, symbol, name) "
                "VALUES (?, 'solana', 'TST', 'Test') ",
                (f"mint-{id(self)}-{self.now.timestamp()}",),
            ).lastrowid
            pid = conn.execute(
                "INSERT INTO printer_pairs (token_id, pair_address, dex, pool_source, "
                "base_token_mint, quote_token_mint) "
                "VALUES (?, ?, 'raydium', 'local', ?, 'So111')",
                (tid, f"pair-{id(self)}-{self.now.timestamp()}", f"mint-{id(self)}-{self.now.timestamp()}"),
            ).lastrowid
            conn.commit()
        finally:
            conn.close()
        return int(tid), int(pid)

    def _base_payload(
        self,
        token_id: int,
        pair_id: int,
        captured_at: str,
        price_usd: float = 0.010,
        source_name: str = "dexscreener",
    ) -> dict:
        return {
            "token_id": token_id,
            "pair_id": pair_id,
            "captured_at": captured_at,
            "tracking_lane": "TRACK_FAST",
            "snapshot_mode": "NORMAL_MODE",
            "price_usd": price_usd,
            "liquidity_usd": 10000.0,
            "source_status": "COMPLETE",
            "data_quality_label": "CLEAN_DATA",
            "source_name": source_name,
            # volume_15m and txns_15m intentionally absent (None) — real pipeline state
        }

    def test_first_snapshot_has_no_derivation(self):
        """Only start snapshot: no eligible pair yet, price_change_15m stays None."""
        tid, pid = self._insert_token_pair()
        payload = self._base_payload(tid, pid, _START_ISO, price_usd=0.010)
        inserted, snap_id = record_token_snapshot(self.db_path, payload, self.now)
        self.assertTrue(inserted)

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT price_change_15m FROM printer_token_snapshots WHERE id = ?",
                (snap_id,),
            ).fetchone()
        finally:
            conn.close()
        self.assertIsNone(row["price_change_15m"])

    def test_end_snapshot_gets_derivation(self):
        """Two snapshots 900s apart: end snapshot should have price_change_15m set."""
        tid, pid = self._insert_token_pair()
        # Record start snapshot
        start_payload = self._base_payload(tid, pid, _START_ISO, price_usd=0.010)
        record_token_snapshot(self.db_path, start_payload, self.now)
        # Record end snapshot
        end_payload = self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015)
        inserted, end_id = record_token_snapshot(self.db_path, end_payload, self.now)
        self.assertTrue(inserted)

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT price_change_15m, normalized_snapshot_payload_json "
                "FROM printer_token_snapshots WHERE id = ?",
                (end_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row["price_change_15m"])
        # 0.010 → 0.015 = +50%
        self.assertAlmostEqual(row["price_change_15m"], 50.0, places=4)

    def test_derived_annotation_in_json(self):
        """End snapshot normalized_snapshot_payload_json carries derivation annotation."""
        tid, pid = self._insert_token_pair()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )
        _, end_id = record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT normalized_snapshot_payload_json FROM printer_token_snapshots WHERE id = ?",
                (end_id,),
            ).fetchone()
        finally:
            conn.close()

        payload = json.loads(row["normalized_snapshot_payload_json"])
        self.assertEqual(payload.get("price_change_15m_source_kind"), "DERIVED_STAGED_SNAPSHOT")
        self.assertIn("price_change_15m_provenance", payload)

    def test_provenance_all_fields_in_json(self):
        """Provenance dict in JSON has all 17 required fields."""
        tid, pid = self._insert_token_pair()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )
        _, end_id = record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT normalized_snapshot_payload_json FROM printer_token_snapshots WHERE id = ?",
                (end_id,),
            ).fetchone()
        finally:
            conn.close()

        payload = json.loads(row["normalized_snapshot_payload_json"])
        prov = payload["price_change_15m_provenance"]
        expected_keys = {
            "derivation_kind", "start_snapshot_id", "end_snapshot_id",
            "token_id", "pair_id", "source_name",
            "start_captured_at", "end_captured_at", "interval_seconds",
            "start_price_usd", "end_price_usd", "derived_price_change_15m",
            "start_data_quality_label", "end_data_quality_label",
            "start_source_status", "end_source_status", "derived_at",
        }
        self.assertEqual(set(prov.keys()), expected_keys)

    def test_update_writes_to_end_snapshot_only(self):
        """Start snapshot's price_change_15m stays None after derivation."""
        tid, pid = self._insert_token_pair()
        _, start_id = record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            start_row = conn.execute(
                "SELECT price_change_15m FROM printer_token_snapshots WHERE id = ?",
                (start_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNone(start_row["price_change_15m"])

    def test_volume_15m_remains_none_after_derivation(self):
        """volume_15m must not be populated by staged derivation."""
        tid, pid = self._insert_token_pair()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )
        _, end_id = record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT volume_15m FROM printer_token_snapshots WHERE id = ?",
                (end_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNone(row["volume_15m"])

    def test_txns_15m_remains_none_after_derivation(self):
        """txns_15m must not be populated by staged derivation."""
        tid, pid = self._insert_token_pair()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )
        _, end_id = record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT txns_15m FROM printer_token_snapshots WHERE id = ?",
                (end_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNone(row["txns_15m"])

    def test_native_source_annotation_not_overwritten(self):
        """If normalized_snapshot_payload_json already has NATIVE_SOURCE, skip derivation."""
        tid, pid = self._insert_token_pair()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )

        # Manually insert the end snapshot with NATIVE_SOURCE annotation
        native_json = json.dumps({"price_change_15m_source_kind": "NATIVE_SOURCE"}, sort_keys=True)
        conn = self._connect()
        try:
            end_id = conn.execute(
                """
                INSERT INTO printer_token_snapshots (
                    token_id, pair_id, captured_at, tracking_lane, snapshot_mode,
                    price_usd, liquidity_usd, source_status, data_quality_label,
                    snapshot_quality_label, normalized_snapshot_payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    tid, pid, _NOW_ISO, "TRACK_FAST", "NORMAL_MODE",
                    0.015, 10000.0, "COMPLETE", "CLEAN_DATA",
                    "PARTIAL_SNAPSHOT", native_json,
                ),
            ).lastrowid
            conn.commit()

            # Now call apply_staged_derivation directly
            normalized = {
                "token_id": tid,
                "pair_id": pid,
                "captured_at": _NOW_ISO,
                "price_usd": 0.015,
                "source_status": "COMPLETE",
                "data_quality_label": "CLEAN_DATA",
                "source_name": "dexscreener",
                "normalized_snapshot_payload_json": native_json,
            }
            updated = apply_staged_derivation(conn, int(end_id), normalized)
            self.assertFalse(updated)

            row = conn.execute(
                "SELECT normalized_snapshot_payload_json FROM printer_token_snapshots WHERE id = ?",
                (end_id,),
            ).fetchone()
        finally:
            conn.close()

        payload = json.loads(row["normalized_snapshot_payload_json"])
        self.assertEqual(payload.get("price_change_15m_source_kind"), "NATIVE_SOURCE")
        self.assertNotIn("price_change_15m_provenance", payload)

    def test_no_memory_rows_created(self):
        """Derivation must not create any printer_memory_windows rows."""
        tid, pid = self._insert_token_pair()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM printer_memory_windows"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, 0)

    def test_no_paper_decision_rows_created(self):
        """Derivation must not create any printer_paper_decisions rows."""
        tid, pid = self._insert_token_pair()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _START_ISO, price_usd=0.010),
            self.now,
        )
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM printer_paper_decisions"
            ).fetchone()[0]
        finally:
            conn.close()

        self.assertEqual(count, 0)

    def test_interval_outside_tolerance_produces_no_derivation(self):
        """If the available start snapshot is outside 720-1080s, no derivation."""
        tid, pid = self._insert_token_pair()
        too_far = (_NOW - timedelta(seconds=1200)).isoformat()
        record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, too_far, price_usd=0.010),
            self.now,
        )
        _, end_id = record_token_snapshot(
            self.db_path,
            self._base_payload(tid, pid, _NOW_ISO, price_usd=0.015),
            self.now,
        )

        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT price_change_15m FROM printer_token_snapshots WHERE id = ?",
                (end_id,),
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNone(row["price_change_15m"])

    def test_duplicate_snapshot_skipped_no_derivation_attempted(self):
        """Duplicate snapshot is skipped (returns False, existing_id); no crash."""
        tid, pid = self._insert_token_pair()
        payload = self._base_payload(tid, pid, _NOW_ISO, price_usd=0.010)
        inserted1, snap_id_1 = record_token_snapshot(self.db_path, payload, self.now)
        inserted2, snap_id_2 = record_token_snapshot(self.db_path, payload, self.now)
        self.assertTrue(inserted1)
        self.assertFalse(inserted2)
        self.assertEqual(snap_id_1, snap_id_2)


# ---------------------------------------------------------------------------
# D. Module-level constant and type tests
# ---------------------------------------------------------------------------

class TestModuleConstants(unittest.TestCase):

    def test_constant_value(self):
        self.assertEqual(
            DERIVATION_KIND_STAGED_SNAPSHOT_PRICE_CHANGE_15M,
            "STAGED_SNAPSHOT_PRICE_CHANGE_15M",
        )

    def test_staged_derivation_result_is_dataclass(self):
        r = StagedDerivationResult(derived_price_change_15m=5.0, provenance={"key": "val"})
        self.assertEqual(r.derived_price_change_15m, 5.0)
        self.assertEqual(r.provenance, {"key": "val"})

    def test_staged_derivation_result_frozen(self):
        r = StagedDerivationResult(derived_price_change_15m=5.0, provenance={})
        with self.assertRaises(Exception):
            r.derived_price_change_15m = 99.0  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
