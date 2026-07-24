"""V2-9.7E.43 $3K graduated discovery and selection front door.

Proves the market-performance front door on fixtures + isolated temporary DBs
only (no live network, no persistent-DB mutation, no lifecycle/pilot/memory):

  FD-01  $2,999.99 fails; $3,000.00 passes (the only numeric threshold)
  FD-02  a $30 graduated pool is retained but never selected
  FD-03  wrong pair / wrong mint / stale / missing / conflicting / non-exact fail closed
  FD-04  token-level liquidity cannot replace exact-pool liquidity
  FD-05  DexScreener cannot prove Pump origin or graduation (registry-only origin)
  FD-06  a current-cycle graduated $3K+ candidate (LATEST) is eligible immediately
  FD-07  a persisted candidate can cross above the floor
  FD-08  a persisted candidate currently below the floor is excluded
  FD-09  bonding-curve candidates remain permanently ineligible (never in registry)
  FD-10  latest/persisted provenance cannot be fabricated
  FD-11  one latest + one persisted selected when both eligible
  FD-12  duplicate channels provide no probability advantage; deterministic replay
  FD-13  source-quality / STNP / cooldown / rotation gates remain intact
  FD-14  no behavioral outcome derived before snapshots; handoff readiness only
  FD-15  atomic-handoff compatibility, integrity, foreign keys, forbidden deltas
"""

from __future__ import annotations

import pathlib
import sqlite3
import sys
import tempfile

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery import graduated_liquidity_front_door as fd
from printer_v1.discovery.graduated_liquidity_front_door import (
    LIQUIDITY_BELOW_SELECTION_FLOOR,
    LIQUIDITY_PROVEN,
    LIQUIDITY_UNPROVEN,
    SELECTION_FLOOR_USD,
    _extract_exact_pair_liquidity,
    enrich_pool_liquidity,
    provenance_for,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    PERSISTED_GRADUATED_CHANNEL,
    record_graduated_candidate,
)

_MINT_A = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
_MINT_B = "GwZvGvVzjWTL1mvpw55KQWztTQvWo3B6ew16N2aspump"
_MINT_C = "3nDcLfEXAJ1M9nQ9c8mS7bqVxUwq4b1rj9F8sJpTpump"
_SIG_A = "ijqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESaaaaaaa"
_SIG_B = "kbqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESbbbbbbb"
_SIG_C = "mcqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESccccccc"
_POOL_A = "6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak"
_POOL_B = "9ZgTJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhAK"
_POOL_C = "8QwTJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhQC"
_NOW = "2026-07-24T00:00:00+00:00"
_SEED = "campaign-seed-v2-9-7e-43"


# --------------------------------------------------------------------------- #
# Helpers                                                                      #
# --------------------------------------------------------------------------- #

def _temp_db():
    path = tempfile.mktemp(suffix=".db")
    apply_migrations(path)
    return path


def _seed_graduated(db, mint, sig, pool, *, block_time=1_784_841_493, now=_NOW):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        record_graduated_candidate(
            conn,
            mint=mint,
            migration_signature=sig,
            pumpswap_pool=pool,
            graduation_block_time=block_time,
            graduation_slot=1,
            now=now,
            discovery_channel=LATEST_GRADUATED_CHANNEL,
        )
        conn.commit()
    finally:
        conn.close()


def _pair_payload(pool, mint, liquidity, *, chain="solana", stale=False):
    payload = {
        "pairs": [
            {
                "chainId": chain,
                "pairAddress": pool,
                "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
                "priceUsd": "0.10",
                "liquidity": ({} if liquidity is None else {"usd": liquidity}),
                "volume": {"m5": 100.0, "h1": 1000.0, "h24": 10000.0},
                "txns": {"m5": {"buys": 3, "sells": 2}},
                "priceChange": {"m5": 1.0},
            }
        ]
    }
    if stale:
        payload["fixture_stale"] = True
    return payload


def _factory(payload_by_pool):
    """Return a transport factory keyed by pool; each returns a fixture transport."""
    def factory(mint, pool):
        return fixture_success_transport(payload_by_pool[pool])
    return factory


def _uniform_factory(liquidity):
    def factory(mint, pool):
        return fixture_success_transport(_pair_payload(pool, mint, liquidity))
    return factory


def _run(db, latest_mints, factory, *, seed=_SEED, batch_seq=1, now=_NOW):
    return fd.run_graduated_liquidity_front_door(
        db,
        cycle_seed=seed,
        latest_mints=set(latest_mints),
        dexscreener_transport_factory=factory,
        now=now,
        batch_seq=batch_seq,
    )


# --------------------------------------------------------------------------- #
# FD-01 — the $3,000 floor is the only numeric threshold                       #
# --------------------------------------------------------------------------- #

class TestFloor:
    def test_fd01_2999_99_fails_3000_00_passes(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        below = _run(db, {_MINT_A}, _uniform_factory(2999.99))
        assert below["candidates"][0]["liquidity"]["status"] == LIQUIDITY_BELOW_SELECTION_FLOOR
        assert below["candidates"][0]["eligible"] is False
        assert below["selected_count"] == 0
        assert below["below_floor_count"] == 1

        db2 = _temp_db()
        _seed_graduated(db2, _MINT_A, _SIG_A, _POOL_A)
        at = _run(db2, {_MINT_A}, _uniform_factory(3000.00))
        assert at["candidates"][0]["liquidity"]["status"] == LIQUIDITY_PROVEN
        assert at["candidates"][0]["eligible"] is True
        assert at["selected_count"] == 1

    def test_fd01_floor_constant(self):
        assert SELECTION_FLOOR_USD == 3000.0


# --------------------------------------------------------------------------- #
# FD-02 — a $30 pool is retained but never selected                            #
# --------------------------------------------------------------------------- #

class TestRetainedNotSelected:
    def test_fd02_thirty_dollar_pool_retained_never_selected(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        r = _run(db, {_MINT_A}, _uniform_factory(30.0))
        assert r["candidate_count"] == 1  # retained as discovery evidence
        assert r["candidates"][0]["liquidity"]["status"] == LIQUIDITY_BELOW_SELECTION_FLOOR
        assert r["candidates"][0]["liquidity"]["liquidity_usd"] == 30.0
        assert r["selected_count"] == 0
        # Still present in the durable registry after the run.
        conn = sqlite3.connect(db)
        n = conn.execute(
            "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
        ).fetchone()[0]
        conn.close()
        assert n == 1


# --------------------------------------------------------------------------- #
# FD-03 / FD-04 — exact-pool identity fail-closed matrix                       #
# --------------------------------------------------------------------------- #

class TestExactPoolFailClosed:
    def _one(self, payload):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        factory = _factory({_POOL_A: payload})
        return _run(db, {_MINT_A}, factory)

    def test_fd03_wrong_pair_fails_closed(self):
        r = self._one(_pair_payload("WRONGPOOLxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", _MINT_A, 9000.0))
        assert r["candidates"][0]["liquidity"]["status"] == LIQUIDITY_UNPROVEN
        assert r["selected_count"] == 0

    def test_fd03_wrong_mint_fails_closed(self):
        r = self._one(_pair_payload(_POOL_A, "WRONGMINTxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", 9000.0))
        assert r["candidates"][0]["liquidity"]["status"] == LIQUIDITY_UNPROVEN
        assert r["candidates"][0]["liquidity"]["reason"] == "LIQUIDITY_MINT_MISMATCH"

    def test_fd03_stale_fails_closed(self):
        r = self._one(_pair_payload(_POOL_A, _MINT_A, 9000.0, stale=True))
        assert r["candidates"][0]["liquidity"]["status"] == LIQUIDITY_UNPROVEN
        assert r["candidates"][0]["liquidity"]["reason"] == "LIQUIDITY_STALE_SOURCE"

    def test_fd03_missing_liquidity_fails_closed_never_zero(self):
        r = self._one(_pair_payload(_POOL_A, _MINT_A, None))
        ev = r["candidates"][0]["liquidity"]
        assert ev["status"] == LIQUIDITY_UNPROVEN
        assert ev["reason"] == "LIQUIDITY_MISSING"
        assert ev["liquidity_usd"] is None  # never coerced to zero

    def test_fd03_non_solana_fails_closed(self):
        # A non-Solana chain pair is filtered by the normalizer and unproven.
        r = self._one(_pair_payload(_POOL_A, _MINT_A, 9000.0, chain="ethereum"))
        assert r["candidates"][0]["liquidity"]["status"] == LIQUIDITY_UNPROVEN

    def test_fd03_empty_pairs_fails_closed(self):
        r = self._one({"pairs": []})
        assert r["candidates"][0]["liquidity"]["status"] == LIQUIDITY_UNPROVEN

    def test_fd03_negative_and_non_finite_fail_closed(self):
        for bad, reason in [(-1.0, "LIQUIDITY_NEGATIVE"), (float("inf"), "LIQUIDITY_NON_FINITE")]:
            value, got = _extract_exact_pair_liquidity(
                [{"chain": "solana", "pair_address": _POOL_A, "token_mint": _MINT_A,
                  "liquidity_usd": bad}],
                mint=_MINT_A, pool=_POOL_A,
            )
            assert value is None and got == reason

    def test_fd04_token_level_cannot_replace_exact_pool(self):
        # The mint exists only on a DIFFERENT pool (token-level style): unproven.
        payload = {
            "pairs": [
                {
                    "chainId": "solana",
                    "pairAddress": _POOL_B,  # not the confirmed pool
                    "baseToken": {"address": _MINT_A, "symbol": "M", "name": "M"},
                    "liquidity": {"usd": 50000.0},
                    "txns": {"m5": {"buys": 1, "sells": 1}},
                }
            ]
        }
        r = self._one(payload)
        ev = r["candidates"][0]["liquidity"]
        assert ev["status"] == LIQUIDITY_UNPROVEN
        assert ev["reason"] == "LIQUIDITY_POOL_MISMATCH_TOKEN_LEVEL"
        assert r["selected_count"] == 0


# --------------------------------------------------------------------------- #
# FD-05 — DexScreener cannot prove Pump origin or graduation                    #
# --------------------------------------------------------------------------- #

class TestDexScreenerNoOrigin:
    def test_fd05_non_registry_mint_never_a_candidate(self):
        db = _temp_db()  # empty registry
        # DexScreener would happily return huge liquidity, but with no graduation
        # evidence in the registry there is no candidate at all.
        r = _run(db, {_MINT_A}, _uniform_factory(1_000_000.0))
        assert r["candidate_count"] == 0
        assert r["selected_count"] == 0

    def test_fd05_liquidity_evidence_has_no_origin_or_graduation_field(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            ev = enrich_pool_liquidity(
                conn, mint=_MINT_A, pumpswap_pool=_POOL_A,
                dexscreener_transport=fixture_success_transport(
                    _pair_payload(_POOL_A, _MINT_A, 9000.0)
                ),
                request_key="k",
            )
            conn.commit()
        finally:
            conn.close()
        d = ev.to_dict()
        for banned in ("origin", "graduation", "pumpfun_origin", "graduated", "confirmed"):
            assert banned not in d


# --------------------------------------------------------------------------- #
# FD-06/07/08 — latest immediate; persisted cross above / below floor          #
# --------------------------------------------------------------------------- #

class TestEligibilityCrossings:
    def test_fd06_latest_3k_eligible_immediately(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        r = _run(db, {_MINT_A}, _uniform_factory(3500.0))
        assert r["candidates"][0]["provenance"] == LATEST_GRADUATED_CHANNEL
        assert r["latest_eligible_count"] == 1
        assert r["selected_count"] == 1

    def test_fd07_persisted_can_cross_above_floor(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        # Not in latest set -> persisted. Below floor first.
        low = _run(db, set(), _uniform_factory(1500.0))
        assert low["candidates"][0]["provenance"] == PERSISTED_GRADUATED_CHANNEL
        assert low["candidates"][0]["eligible"] is False
        # Later clean observation crosses above the floor -> eligible.
        high = _run(db, set(), _uniform_factory(3200.0))
        assert high["candidates"][0]["eligible"] is True
        assert high["persisted_eligible_count"] == 1

    def test_fd08_persisted_below_floor_excluded(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        r = _run(db, set(), _uniform_factory(2999.99))
        assert r["candidates"][0]["provenance"] == PERSISTED_GRADUATED_CHANNEL
        assert r["candidates"][0]["eligible"] is False
        assert r["selected_count"] == 0


# --------------------------------------------------------------------------- #
# FD-09 — bonding-curve candidates never enter the registry / selection        #
# --------------------------------------------------------------------------- #

class TestBondingCurveIneligible:
    def test_fd09_registry_only_holds_graduated(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        conn = sqlite3.connect(db)
        # The registry CHECK constraint permits only PUMPSWAP_GRADUATED_CONFIRMED.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE printer_pumpswap_graduated_candidate_registry "
                "SET lifecycle_state='PUMP_BONDING_CURVE_ACTIVE' WHERE mint_identity=?",
                (_MINT_A,),
            )
        conn.close()


# --------------------------------------------------------------------------- #
# FD-10 — provenance cannot be fabricated                                      #
# --------------------------------------------------------------------------- #

class TestProvenanceTruthful:
    def test_fd10_provenance_derived_only_from_current_cycle_set(self):
        assert provenance_for(_MINT_A, {_MINT_A}) == LATEST_GRADUATED_CHANNEL
        assert provenance_for(_MINT_A, set()) == PERSISTED_GRADUATED_CHANNEL
        assert provenance_for(_MINT_A, {_MINT_B}) == PERSISTED_GRADUATED_CHANNEL

    def test_fd10_same_registry_row_flips_by_cycle_set_not_label(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        as_latest = _run(db, {_MINT_A}, _uniform_factory(5000.0))
        as_persisted = _run(db, set(), _uniform_factory(5000.0))
        assert as_latest["candidates"][0]["provenance"] == LATEST_GRADUATED_CHANNEL
        assert as_persisted["candidates"][0]["provenance"] == PERSISTED_GRADUATED_CHANNEL


# --------------------------------------------------------------------------- #
# FD-11/12 — mixed two-slot + determinism + no duplicate boost                 #
# --------------------------------------------------------------------------- #

class TestMixedTwoSlot:
    def _mixed_db(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        _seed_graduated(db, _MINT_B, _SIG_B, _POOL_B)
        return db

    def test_fd11_one_latest_one_persisted_selected(self):
        db = self._mixed_db()
        # A is current-cycle (latest); B is persisted; both above floor.
        r = _run(db, {_MINT_A}, _uniform_factory(4000.0))
        assert r["mix_state"] == "MIXED_TWO_SLOT"
        assert r["selected_count"] == 2
        assert r["selected_latest"] is not None
        assert r["selected_persisted"] is not None
        assert r["selected_latest"]["provenance"] == LATEST_GRADUATED_CHANNEL
        assert r["selected_persisted"]["provenance"] == PERSISTED_GRADUATED_CHANNEL
        assert r["selected_latest"]["mint"] == _MINT_A
        assert r["selected_persisted"]["mint"] == _MINT_B

    def test_fd12_deterministic_replay(self):
        db = self._mixed_db()
        r1 = _run(db, {_MINT_A}, _uniform_factory(4000.0))
        r2 = _run(db, {_MINT_A}, _uniform_factory(4000.0))
        assert r1["selected_pair_identity"] == r2["selected_pair_identity"]

    def test_fd12_liquidity_magnitude_does_not_affect_selection(self):
        # Two eligible persisted candidates with very different (above-floor)
        # liquidity: selection must not prefer the larger one — it is seeded uniform.
        db = _temp_db()
        _seed_graduated(db, _MINT_B, _SIG_B, _POOL_B)
        _seed_graduated(db, _MINT_C, _SIG_C, _POOL_C)

        def factory(mint, pool):
            liq = 3001.0 if pool == _POOL_B else 999999.0
            return fixture_success_transport(_pair_payload(pool, mint, liq))

        picks = set()
        for seed in ("s1", "s2", "s3", "s4", "s5", "s6"):
            r = fd.run_graduated_liquidity_front_door(
                db, cycle_seed=seed, latest_mints=set(),
                dexscreener_transport_factory=factory, now=_NOW,
            )
            assert r["mix_state"] == "SINGLE_CATEGORY_DEGRADED"
            picks.add(r["selected"][0]["mint"])
        # Across seeds both mints are pickable -> the huge-liquidity mint has no lock.
        assert picks == {_MINT_B, _MINT_C}


# --------------------------------------------------------------------------- #
# FD-13 — existing gates remain intact                                         #
# --------------------------------------------------------------------------- #

class TestGatesIntact:
    def test_fd13_source_quality_failed_result_is_unproven(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)

        def factory(mint, pool):
            def transport(context):
                return {"fixture_status": "failure",
                        "failure_type": "dexscreener_http_server_error",
                        "failure_message": "boom"}
            return transport

        r = _run(db, {_MINT_A}, factory)
        assert r["candidates"][0]["liquidity"]["status"] == LIQUIDITY_UNPROVEN
        assert r["selected_count"] == 0

    def test_fd13_cooldown_gate_rejects_recently_selected(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        conn = sqlite3.connect(db)
        conn.execute(
            """
            INSERT INTO printer_selection_rotation_state(
                token_mint, pair_address, last_selected_batch_seq,
                selection_count, created_at, updated_at
            ) VALUES (?, ?, ?, 1, ?, ?)
            """,
            (_MINT_A, _POOL_A, 2, _NOW, _NOW),
        )
        conn.commit()
        conn.close()
        # current batch_seq=3, last=2 -> batches_since=1 < window 3 -> cooldown reject.
        r = _run(db, {_MINT_A}, _uniform_factory(9000.0), batch_seq=3)
        assert r["candidates"][0]["eligible"] is False
        assert "COOLDOWN" in (r["candidates"][0]["rejection"] or "")
        assert r["selected_count"] == 0


# --------------------------------------------------------------------------- #
# FD-14/15 — no behavioral outcome; handoff readiness; integrity              #
# --------------------------------------------------------------------------- #

class TestBoundaryAndIntegrity:
    def test_fd14_no_behavioral_outcome_derived(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        _seed_graduated(db, _MINT_B, _SIG_B, _POOL_B)
        r = _run(db, {_MINT_A}, _uniform_factory(4000.0))
        blob = repr(r)
        for behavioral in ("DUMP", "DECAY", "REVIVAL", "CONSOLIDATION"):
            assert behavioral not in blob
        h = r["handoff_readiness"]
        assert h["tracking_enqueued"] is False
        assert h["scheduler_started"] is False
        assert h["lifecycle_started"] is False
        assert h["snapshot_started"] is False

    def test_fd15_handoff_compatibility_and_integrity(self):
        db = _temp_db()
        _seed_graduated(db, _MINT_A, _SIG_A, _POOL_A)
        _seed_graduated(db, _MINT_B, _SIG_B, _POOL_B)
        r = _run(db, {_MINT_A}, _uniform_factory(4000.0))
        h = r["handoff_readiness"]
        assert h["atomic_two_slot_ready"] is True
        assert h["selected_slot_count"] == 2
        assert all(c["compatible"] for c in h["checks"])
        assert r["forbidden_delta_total"] == 0
        assert r["integrity_check"] == "ok"
        assert r["foreign_key_violations"] == 0
        # No tracking / lifecycle rows created.
        conn = sqlite3.connect(db)
        for table in ("printer_tracking_queue", "printer_memory_factory_runs"):
            try:
                n = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.OperationalError:
                n = 0
            assert n == 0, table
        conn.close()
