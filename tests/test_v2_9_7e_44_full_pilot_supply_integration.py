"""V2-9.7E.44 FULL_PILOT graduated candidate-supply integration.

Proves, on fixtures + isolated temporary DBs only (no live network, no
persistent-DB mutation, no lifecycle/pilot/memory), that the adopted E.42
direct-migration discovery and E.43 ``$3,000`` exact-pool front door are wired
into the canonical ``run_operational`` (FULL_PILOT) candidate-supply path:

  SI-01  build_graduated_supply composes discovery + front door → one LATEST +
         one PERSISTED $3K+ candidate with the real derived Pump bonding curve
         and a faithful graduation proof
  SI-02  a below-floor LATEST candidate is excluded → not ready →
         BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL (market supply, not a defect)
  SI-03  run_operational(..., graduated_supply=..., stop_before_lifecycle=True)
         admits exactly the two graduated candidates, runs holder eligibility, and
         returns atomic two-slot readiness with lifecycle_started False and zero
         forbidden-capability rows
  SI-04  default run_operational (no supply, no live transport) is unchanged:
         cold-start → BLOCKED_INSUFFICIENT_GRADUATED_POOL
  SI-05  the derived bonding curve is the real Pump PDA (not fabricated)
"""

from __future__ import annotations

import base64
from dataclasses import replace
import pathlib
import sqlite3
import sys
import tempfile
from unittest import mock

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery.combined_executor import (
    FixtureOriginProof,
    FixturePumpSwapProof,
    PUMPSWAP_PROGRAM_ID,
)
from printer_v1.operator_cli.abstract_campaign_command import (
    CENTRAL_SCHEDULER_OWNER,
    SOURCE_GOVERNOR_OWNER,
    OwnerPort,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    AuthoritativeLiveOperationalCampaignOwner,
    BLOCKED_INSUFFICIENT_GRADUATED_POOL,
)
from printer_v1.operator_cli.graduated_supply_front_door import (
    BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL,
    GraduatedSupply,
    build_graduated_supply,
    derive_bonding_curve,
)
from printer_v1.sources import pump_migration as pm
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpfun_direct import (
    PUMP_PROGRAM_ID,
    _b58decode,
    derive_program_address,
)
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    lookup_graduated_candidate,
    record_graduated_candidate,
)

import test_v2_9_7e_8_origin_to_lifecycle_integration as e8
from test_v2_9_7e_11_authoritative_live_operational_campaign import _FakePumpTransport

GOV = OwnerPort(SOURCE_GOVERNOR_OWNER, True)
SCH = OwnerPort(CENTRAL_SCHEDULER_OWNER, True)

# Real Pump.fun mints (…pump suffix) so base58 decode + PDA derivation are exact.
_MINT_LATEST = "4tNCRgigHBPiMsPfrCaU1kE6gGofxgXLmEq8mRK1pump"
_MINT_PERSISTED = "4FN5PSaprS73Z2SRGx2HG9eaES1yVURMU5yAPpDQpump"
_SIG_LATEST = "ijqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESaaaaaaa"
_SIG_PERSISTED = "kbqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESbbbbbbb"
_POOL_LATEST = "BDhvEqa1KjHBsNSFxN9Np4t3CLZjaCvDtCRjrqsbQ21p"
_POOL_PERSISTED = "9yuowVdGRZ35yM339cjyTWfhAdJJVPJqPKGHhyCXG3fo"
_NOW = "2026-07-24T00:00:00+00:00"
_SEED = "v2-9-7e-44-seed"


# --------------------------------------------------------------------------- #
# Fixtures                                                                     #
# --------------------------------------------------------------------------- #

def _temp_db() -> str:
    handle = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    handle.close()
    apply_migrations(handle.name)
    return handle.name


def _pool_acct(mint: str) -> dict:
    data = b"\x01" * 43 + _b58decode(mint) + b"\x02" * 226
    return {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "data": [base64.b64encode(data).decode(), "base64"],
    }


def _migration_tx(pool: str, mint: str, *, block_time=1_783_886_668, slot=432_499_503) -> dict:
    static = [pool, mint, PUMP_PROGRAM_ID, PUMPSWAP_AMM_PROGRAM_ID]
    return {
        "blockTime": block_time,
        "slot": slot,
        "transaction": {"message": {"accountKeys": static}},
        "meta": {"err": None, "loadedAddresses": {"writable": [], "readonly": []}},
    }


def _mock_rpc(by_sig):
    def fake_rpc(rpc_url, method, params, *, timeout_seconds):
        if method == "getTransaction":
            tx, _infos = by_sig.get(params[0], (None, {}))
            return {"result": tx}
        if method == "getMultipleAccounts":
            chunk = params[0]
            for _sig, (_tx, infos) in by_sig.items():
                if any(k in infos for k in chunk):
                    return {"result": {"value": [infos.get(k) for k in chunk]}}
            return {"result": {"value": [None for _ in chunk]}}
        return {"result": None}
    return mock.patch.object(pm, "_rpc_post", fake_rpc)


def _migration_transport(events):
    def transport(context):
        return {"events": events, "subscription_method": "subscribeMigration"}
    return transport


def _pair_payload(pool: str, mint: str, liquidity: float) -> dict:
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": pool,
                "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
                "priceUsd": "0.10",
                "liquidity": {"usd": liquidity},
                "volume": {"m5": 100.0, "h1": 1000.0, "h24": 10000.0},
                "txns": {"m5": {"buys": 3, "sells": 2}},
                "priceChange": {"m5": 1.0},
            }
        ]
    }


def _dexscreener_factory(liquidity_by_pool):
    def factory(mint, pool):
        return fixture_success_transport(_pair_payload(pool, mint, liquidity_by_pool[pool]))
    return factory


def _seed_persisted(db: str) -> None:
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        record_graduated_candidate(
            conn,
            mint=_MINT_PERSISTED,
            migration_signature=_SIG_PERSISTED,
            pumpswap_pool=_POOL_PERSISTED,
            graduation_block_time=1_783_800_000,
            graduation_slot=432_400_000,
            now="2026-07-23T00:00:00+00:00",  # a prior cycle → PERSISTED provenance
            discovery_channel=LATEST_GRADUATED_CHANNEL,
        )
        conn.commit()
    finally:
        conn.close()


def _build(db: str, *, latest_liq: float, persisted_liq: float) -> GraduatedSupply:
    by_sig = {_SIG_LATEST: (_migration_tx(_POOL_LATEST, _MINT_LATEST), {_POOL_LATEST: _pool_acct(_MINT_LATEST)})}
    with _mock_rpc(by_sig):
        return build_graduated_supply(
            db,
            cycle_seed=_SEED,
            migration_transport=_migration_transport(
                [{"mint": _MINT_LATEST, "signature": _SIG_LATEST, "newRaydiumPool": _POOL_LATEST}]
            ),
            dexscreener_transport_factory=_dexscreener_factory(
                {_POOL_LATEST: latest_liq, _POOL_PERSISTED: persisted_liq}
            ),
            now=_NOW,
        )


# --------------------------------------------------------------------------- #
# SI-01 / SI-05 — composition yields the mixed pair with real bonding curve     #
# --------------------------------------------------------------------------- #

class TestComposition:
    def test_si01_mixed_pair_ready(self):
        db = _temp_db()
        _seed_persisted(db)
        supply = _build(db, latest_liq=9_723.71, persisted_liq=15_350.10)

        assert supply.ready is True
        assert supply.terminal == "GRADUATED_SUPPLY_READY"
        assert supply.selected_latest is not None
        assert supply.selected_persisted is not None
        assert set(supply.graduation_proofs) == {_MINT_LATEST, _MINT_PERSISTED}
        assert len(supply.graduated_supply) == 2

        # Graduation proofs bind the exact confirmed PumpSwap pools.
        assert supply.graduation_proofs[_MINT_LATEST].pool_address == _POOL_LATEST
        assert supply.graduation_proofs[_MINT_PERSISTED].pool_address == _POOL_PERSISTED
        assert all(p.confirmed and not p.ambiguous for p in supply.graduation_proofs.values())
        assert all(p.program_id == PUMPSWAP_PROGRAM_ID for p in supply.graduation_proofs.values())

        # Origin carriers use the real derived Pump bonding-curve PDA and the
        # on-chain migration signature (graduation-lineage proof).
        by_mint = {p.mint: p for p in supply.graduated_supply}
        assert by_mint[_MINT_LATEST].signature == _SIG_LATEST
        assert by_mint[_MINT_LATEST].bonding_curve == derive_bonding_curve(_MINT_LATEST)
        assert by_mint[_MINT_LATEST].confirmed is True

        assert supply.handoff_readiness  # atomic-handoff compatibility present
        assert supply.diagnostics["below_floor_count"] == 0
        assert supply.diagnostics["discovery_forbidden_delta_total"] == 0
        assert supply.diagnostics["front_door_forbidden_delta_total"] == 0
        assert supply.diagnostics["foreign_key_violations"] == 0
        assert supply.diagnostics["integrity_check"] == "ok"

    def test_si05_bonding_curve_is_real_pda_not_fabricated(self):
        expected = derive_program_address(
            (b"bonding-curve", _b58decode(_MINT_LATEST)), PUMP_PROGRAM_ID
        )
        assert derive_bonding_curve(_MINT_LATEST) == expected
        # A fabricated marker would not equal the deterministic PDA.
        assert derive_bonding_curve(_MINT_LATEST) != f"pump-migrated:{_MINT_LATEST}"


# --------------------------------------------------------------------------- #
# SI-02 — below-floor candidate excluded → honest insufficient terminal        #
# --------------------------------------------------------------------------- #

class TestBelowFloorExcluded:
    def test_si02_below_floor_latest_excluded_not_ready(self):
        db = _temp_db()
        _seed_persisted(db)
        supply = _build(db, latest_liq=8.70, persisted_liq=15_350.10)

        assert supply.ready is False
        assert supply.terminal == BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL
        assert supply.selected_latest is None  # below-floor LATEST not selected
        assert supply.diagnostics["below_floor_count"] == 1
        # The below-floor candidate is still retained in the durable registry.
        conn = sqlite3.connect(db)
        n = conn.execute(
            "SELECT COUNT(*) FROM printer_pumpswap_graduated_candidate_registry"
        ).fetchone()[0]
        conn.close()
        assert n == 2


# --------------------------------------------------------------------------- #
# SI-03 / SI-04 — run_operational wiring + default-unchanged                    #
# --------------------------------------------------------------------------- #

def _clean_goplus_context():
    from printer_v1.sources.governed_execution import build_fixture_source_adapter

    def safety(**kwargs):
        mint = kwargs.get("token_mint")
        return build_fixture_source_adapter(
            "goplus",
            fixture_payload={
                "token_mint": mint,
                "mint_authority": None,
                "freeze_authority": None,
                "metadata_mutable": False,
                "total_supply": "1000000000",
                "top_10_holders": [{"percent": "3"} for _ in range(10)],
                "lp_info": [{"locked": True}],
                "risk_flags": [],
            },
        )

    return {"goplus": safety}


class WiringTests(e8._IntegrationBase):
    """SI-03 / SI-04: run_operational consumes the supply and stops before lifecycle."""

    def _supply(self) -> GraduatedSupply:
        proofs = {
            _MINT_LATEST: FixturePumpSwapProof(
                mint=_MINT_LATEST, pool_address=_POOL_LATEST
            ),
            _MINT_PERSISTED: FixturePumpSwapProof(
                mint=_MINT_PERSISTED, pool_address=_POOL_PERSISTED
            ),
        }
        supply = (
            FixtureOriginProof(
                mint=_MINT_LATEST, signature=_SIG_LATEST, slot=432_499_503,
                block_time=e8_now_epoch(), bonding_curve=derive_bonding_curve(_MINT_LATEST),
                confirmed=True,
            ),
            FixtureOriginProof(
                mint=_MINT_PERSISTED, signature=_SIG_PERSISTED, slot=432_400_000,
                block_time=e8_now_epoch(), bonding_curve=derive_bonding_curve(_MINT_PERSISTED),
                confirmed=True,
            ),
        )
        return GraduatedSupply(
            ready=True,
            terminal="GRADUATED_SUPPLY_READY",
            graduated_supply=supply,
            graduation_proofs=proofs,
            selected_latest={"mint": _MINT_LATEST, "pool": _POOL_LATEST},
            selected_persisted={"mint": _MINT_PERSISTED, "pool": _POOL_PERSISTED},
            handoff_readiness={"atomic_two_slot_ready": True},
            discovery_report={},
            front_door_report={},
            diagnostics={"selection_floor_usd": 3000.0},
        )

    def test_si03_stop_before_lifecycle_atomic_ready(self):
        owner = AuthoritativeLiveOperationalCampaignOwner()
        result = owner.run_operational(
            command=self.command,
            pump_transport=_FakePumpTransport([], {}),
            secondary_transport=None,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e44-wire",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs={"context_adapter_factories": _clean_goplus_context()},
            graduated_supply=self._supply(),
            stop_before_lifecycle=True,
        )
        assert result.lifecycle_started is False
        life = result.lifecycle
        assert life["stopped_before_lifecycle"] is True
        assert life["graduated_candidate_count"] == 2
        assert life["holder_eligible_count"] == 2
        assert life["atomic_two_slot_ready"] is True
        assert life["stop_reason"] == "PRE_LIFECYCLE_ATOMIC_TWO_SLOT_READY"
        # No lifecycle / memory / paper rows created.
        conn = sqlite3.connect(self.db)
        try:
            for table in (
                "printer_memory_windows",
                "printer_episodes",
                "printer_paper_decisions",
                "printer_paper_positions",
            ):
                assert int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) == 0
            assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()

    def test_e46_holder_reserve_writes_readiness_before_lifecycle(self):
        base = self._supply()
        candidates = {
            _MINT_LATEST.lower(): {
                "mint": _MINT_LATEST,
                "pool": _POOL_LATEST,
                "market_identity": f"solana-mainnet:pumpswap:{_POOL_LATEST}",
                "provenance": "LATEST_GRADUATED",
                "liquidity": {"liquidity_usd": 5000.0},
            },
            _MINT_PERSISTED.lower(): {
                "mint": _MINT_PERSISTED,
                "pool": _POOL_PERSISTED,
                "market_identity": f"solana-mainnet:pumpswap:{_POOL_PERSISTED}",
                "provenance": "PERSISTED_GRADUATED",
                "liquidity": {"liquidity_usd": 6000.0},
            },
        }
        supply = replace(
            base,
            holder_reserve_supply=base.graduated_supply,
            holder_reserve_candidates=candidates,
            front_door_report={"generated_at": e8.NOW},
        )
        result = AuthoritativeLiveOperationalCampaignOwner().run_operational(
            command=self.command,
            pump_transport=_FakePumpTransport([], {}),
            secondary_transport=None,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e46-wire",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs={"context_adapter_factories": _clean_goplus_context()},
            graduated_supply=supply,
            stop_before_lifecycle=True,
        )
        assert result.lifecycle["stop_reason"] == "PILOT_INPUT_READY"
        assert result.lifecycle["pilot_input_readiness"]["readiness_state"] == "PILOT_INPUT_READY"
        conn = sqlite3.connect(self.db)
        try:
            assert conn.execute(
                "SELECT COUNT(*) FROM printer_pilot_input_readiness_bundle"
            ).fetchone()[0] == 1
        finally:
            conn.close()

    def test_si04_default_no_supply_cold_start_blocked(self):
        owner = AuthoritativeLiveOperationalCampaignOwner()
        result = owner.run_operational(
            command=self.command,
            pump_transport=_FakePumpTransport([], {}),
            secondary_transport=None,
            source_governor=GOV,
            central_scheduler=SCH,
            selection_seed="e44-default",
            cycle_id="cyc",
            cycle_cutoff=e8.CUTOFF,
            evaluated_at=e8.NOW,
            backup_path=self.backup,
            lifecycle_kwargs={},
        )
        assert result.lifecycle_started is False
        assert result.lifecycle["stop_reason"] == BLOCKED_INSUFFICIENT_GRADUATED_POOL


def e8_now_epoch() -> int:
    from datetime import datetime

    return int(datetime.fromisoformat(e8.NOW).timestamp())
