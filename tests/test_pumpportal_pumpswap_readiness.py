"""Stage 3 — PumpPortal migration + PumpSwap confirmation readiness.

Fixture-level proofs for the minimal governed paths that make PumpPortal
migration and PumpSwap pool confirmation usable for discovery/selection.

  PR-01  migration transport builds and requests subscribeMigration
  PR-02  launch transport still requests subscribeNewToken (unchanged)
  PR-03  build_pumpportal_live_transport rejects an unaddressable request_kind
  PR-04  migration event normalizes: mint+pool kept, token_created_at NEVER set
  PR-05  launch event without timestamp -> OBSERVED_LIVE_LAUNCH, no token_created_at
  PR-06  migration payload normalizes COMPLETE with dex=raydium
  PR-07  migration event with a stray timestamp still yields token_created_at=None
  PR-08  PumpSwap valid pool confirmation normalizes COMPLETE
  PR-09  PumpSwap malformed payload fails closed
  PR-10  PumpSwap non-Solana pool fails closed
  PR-11  PumpSwap missing mint/pool identity fails closed
  PR-12  PumpSwap disallowed request kind fails closed
  PR-13  migration catalog entry is READY and launch+migration both planned

No live fetching, DB mutation, memory, retrieval, paper decisions, positions,
trades, audits, or PnL.
"""

from __future__ import annotations

import json
import pathlib
import sys
from types import SimpleNamespace

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.pumpportal import (
    _normalize_pumpportal_event,
    build_pumpportal_live_transport,
    build_pumpportal_migration_transport,
    normalize_pumpportal_payload,
)
from printer_v1.sources.pumpswap import normalize_pumpswap_payload


# --- Fake websockets module so we can drive the transport without a network ---

class _FakeWS:
    def __init__(self, frames):
        self._frames = list(frames)
        self.sent = []

    async def send(self, msg):
        self.sent.append(msg)

    async def recv(self):
        if self._frames:
            return self._frames.pop(0)
        raise AssertionError("no more frames")

    async def close(self):
        pass


def _make_fake_ws_module(frames, capture):
    import types as _t

    mod = _t.ModuleType("websockets")

    async def _connect(url, *a, **k):
        ws = _FakeWS(frames)
        capture["ws"] = ws
        capture["url"] = url
        return ws

    mod.connect = _connect
    return mod


class TestMigrationTransport:
    def test_pr01_migration_transport_subscribes_migration(self):
        capture = {}
        frames = [json.dumps({"mint": "MigMint1", "newRaydiumPool": "Pool1"})]
        fake = _make_fake_ws_module(frames, capture)
        with pytest.MonkeyPatch.context() as mp:
            mp.setitem(sys.modules, "websockets", fake)
            transport = build_pumpportal_migration_transport(max_events=1, duration_seconds=5.0)
            payload = transport(None)
        assert payload["subscription_method"] == "subscribeMigration"
        assert json.loads(capture["ws"].sent[0]) == {"method": "subscribeMigration"}
        assert len(payload["events"]) == 1

    def test_pr02_launch_transport_subscribes_new_token(self):
        capture = {}
        frames = [json.dumps({"mint": "LaunchMint1"})]
        fake = _make_fake_ws_module(frames, capture)
        with pytest.MonkeyPatch.context() as mp:
            mp.setitem(sys.modules, "websockets", fake)
            transport = build_pumpportal_live_transport(max_events=1, duration_seconds=5.0)
            payload = transport(None)
        assert payload["subscription_method"] == "subscribeNewToken"
        assert json.loads(capture["ws"].sent[0]) == {"method": "subscribeNewToken"}

    def test_pr03_unaddressable_request_kind_rejected(self):
        with pytest.raises(ValueError, match="addressable"):
            build_pumpportal_live_transport(request_kind="subscribeAccountTrade")


class TestTimestampSemantics:
    def test_pr04_migration_event_never_sets_token_created_at(self):
        ev = {"mint": "MigMint1", "newRaydiumPool": "Pool1", "symbol": "MIG", "name": "Mig"}
        r = _normalize_pumpportal_event(ev, "pumpfun_migration_stream")
        assert r is not None
        assert r["token_created_at"] is None
        assert r["live_observed_launch"] is False
        assert r["dex"] == "raydium"
        assert r["pairAddress"] == "Pool1"

    def test_pr05_launch_no_timestamp_is_observed_live_launch(self):
        ev = {"mint": "LnMint1", "bondingCurveKey": "Curve1", "symbol": "L", "name": "L",
              "vSolInBondingCurve": 12.0}
        r = _normalize_pumpportal_event(ev, "pumpfun_launch_stream")
        assert r["live_observed_launch"] is True
        assert r["token_created_at"] is None

    def test_pr06_migration_payload_complete_dex_raydium(self):
        payload = {"events": [{"mint": "MigMint1", "newRaydiumPool": "Pool1"}],
                   "subscription_method": "subscribeMigration"}
        result = normalize_pumpportal_payload(payload, request_kind="pumpfun_migration_stream")
        assert result.source_status == SourceStatus.COMPLETE
        tok = result.normalized_payload["tokens"][0]
        assert tok["dex"] == "raydium"
        assert tok["token_created_at"] is None

    def test_pr07_migration_stray_timestamp_ignored(self):
        # Even if a migration event carried a timestamp field, it must not become
        # token_created_at — migration time is never token creation time.
        ev = {"mint": "MigMint1", "newRaydiumPool": "Pool1", "timestamp": "2026-07-12T10:00:00Z"}
        r = _normalize_pumpportal_event(ev, "pumpfun_migration_stream")
        assert r["token_created_at"] is None


def _pumpswap_pool(chain="solana", base_mint="GradMint1", pool="GradPool1"):
    return {
        "chain": chain,
        "base_mint": base_mint,
        "pool_address": pool,
        "symbol": "GRAD",
        "name": "Graduated",
        "liquidity_usd": 8000.0,
        "price_usd": 0.002,
        "volume_1h": 1500.0,
        "txns_1h": 20,
    }


class TestPumpSwapConfirmation:
    def test_pr08_valid_pool_confirmation_complete(self):
        payload = {"pools": [_pumpswap_pool()]}
        result = normalize_pumpswap_payload(payload, request_kind="pumpswap_pool_confirmation")
        assert result.source_status == SourceStatus.COMPLETE
        tok = result.normalized_payload["tokens"][0]
        assert tok["dex"] == "pumpswap"
        assert tok["chain"] == "solana"
        assert tok["mint"] == "GradMint1"
        assert tok["pairAddress"] == "GradPool1"
        # confirmation must not carry a token creation timestamp
        assert "token_created_at" not in tok

    def test_pr09_malformed_payload_fails_closed(self):
        # No tokens/pools content at all -> empty pool list -> fails closed.
        result = normalize_pumpswap_payload({"nonsense": True}, request_kind="pumpswap_pool_confirmation")
        assert result.source_status == SourceStatus.FAILED
        assert result.failure_type == "pumpswap_no_valid_solana_pools"

    def test_pr09b_non_list_pools_fails_closed(self):
        # A non-list "pools" value -> missing_pool_list fail-closed path.
        result = normalize_pumpswap_payload({"pools": "not-a-list"}, request_kind="pumpswap_pool_confirmation")
        assert result.source_status == SourceStatus.FAILED
        assert result.failure_type == "pumpswap_missing_pool_list"

    def test_pr10_non_solana_pool_fails_closed(self):
        payload = {"pools": [_pumpswap_pool(chain="ethereum")]}
        result = normalize_pumpswap_payload(payload, request_kind="pumpswap_pool_confirmation")
        assert result.source_status == SourceStatus.FAILED
        assert result.failure_type == "pumpswap_no_valid_solana_pools"

    def test_pr11_missing_identity_fails_closed(self):
        payload = {"pools": [{"chain": "solana", "symbol": "X"}]}  # no mint/pool
        result = normalize_pumpswap_payload(payload, request_kind="pumpswap_pool_confirmation")
        assert result.source_status == SourceStatus.FAILED

    def test_pr12_disallowed_request_kind_fails_closed(self):
        payload = {"pools": [_pumpswap_pool()]}
        result = normalize_pumpswap_payload(payload, request_kind="pumpswap_execute_swap")
        assert result.source_status == SourceStatus.FAILED
        assert result.failure_type == "pumpswap_request_kind_not_allowed"


class TestCatalogReadiness:
    def test_pr13_migration_catalog_entry_is_ready(self):
        from printer_v1.operator_cli.commands import (
            _SOURCE_REQUEST_PLAN_CATALOG,
            _PLAN_STATUS_READY,
            _build_source_request_plan,
        )
        entries = dict(_SOURCE_REQUEST_PLAN_CATALOG["pumpportal"])
        assert entries["pumpfun_launch_stream"] == _PLAN_STATUS_READY
        assert entries["pumpfun_migration_stream"] == _PLAN_STATUS_READY
        plan = _build_source_request_plan("pumpportal", "pumpfun_migration_stream", 2)
        assert plan[0]["request_kind"] == "pumpfun_migration_stream"
        assert plan[0]["status"] == _PLAN_STATUS_READY
