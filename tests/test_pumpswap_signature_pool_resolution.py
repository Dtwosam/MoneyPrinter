"""Governed PumpSwap pool resolution from a migration signature (read-only).

Resolves the unique PumpSwap pool account referenced by a migration transaction
using only Solana RPC evidence (getTransaction + getMultipleAccounts), with no
DexScreener dependency. Migration block time is migration evidence only and
never becomes token_created_at.

  SR-01  collect_transaction_account_keys: static + ALT-loaded, dedup, jsonParsed
  SR-02  resolve unique pool -> resolved with block time + provenance
  SR-03  zero matching pools -> fails closed
  SR-04  ambiguous (multiple matching pools) -> fails closed
  SR-05  missing transaction -> fails closed
  SR-06  program-owned-but-non-pool (config) account is excluded
  SR-07  transport end-to-end (mocked RPC) -> COMPLETE, no token_created_at
  SR-08  transport fails closed when transaction not found
  SR-09  transport fails closed on ambiguous, normalizes to FAILED
  SR-10  normalize carries resolution provenance; migration time is evidence-only
  SR-11  registry + routing wiring
  SR-12  no score/rank fields; resolver does not import DexScreener

No live network (RPC mocked), no DB mutation, no memory/retrieval/decisions/PnL.
"""

from __future__ import annotations

import base64
import pathlib
import sys

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.contracts.enums import SourceStatus
from printer_v1.sources import pumpswap as ps
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _b58decode,
    build_pumpswap_signature_pool_resolver_transport,
    collect_transaction_account_keys,
    normalize_pumpswap_confirmation_payload,
    normalize_pumpswap_payload,
    resolve_pumpswap_pool_from_transaction,
)

_MINT = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
_SIG = "ijqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usES3Zx5QMs"


def _pool_acct(mint=_MINT):
    data = b"\x01" * 43 + _b58decode(mint) + b"\x02" * 226
    return {"owner": PUMPSWAP_AMM_PROGRAM_ID, "data": [base64.b64encode(data).decode(), "base64"]}


def _config_acct():
    # PumpSwap-owned but not a pool (no mint at offset 43; different size).
    return {"owner": PUMPSWAP_AMM_PROGRAM_ID, "data": [base64.b64encode(b"\x09" * 907).decode(), "base64"]}


def _foreign_acct():
    return {"owner": "11111111111111111111111111111111", "data": [base64.b64encode(b"\x00" * 20).decode(), "base64"]}


def _tx(keys_static, writable=None, readonly=None, block_time=1_783_886_668, slot=432_499_503):
    return {
        "blockTime": block_time,
        "slot": slot,
        "transaction": {"message": {"accountKeys": keys_static}},
        "meta": {"loadedAddresses": {"writable": writable or [], "readonly": readonly or []}},
    }


class TestAccountKeyCollection:
    def test_sr01_collects_static_and_loaded_dedup(self):
        tx = _tx(["A", {"pubkey": "B"}, "A"], writable=["C"], readonly=["D", "C"])
        keys = collect_transaction_account_keys(tx)
        assert keys == ["A", "B", "C", "D"]


class TestResolver:
    def test_sr02_resolve_unique_pool(self):
        tx = _tx(["POOL", "CFG", "PROG"], writable=["LW"], readonly=["LR"])
        infos = {"POOL": _pool_acct(), "CFG": _config_acct(), "PROG": None, "LW": _foreign_acct(), "LR": _config_acct()}
        r = resolve_pumpswap_pool_from_transaction(tx, infos, expected_mint=_MINT)
        assert r["resolved"] is True
        assert r["pool_address"] == "POOL"
        assert r["mint_matched_count"] == 1
        assert r["program_owned_count"] == 3  # POOL + CFG + LR
        assert r["migration_block_time"] == 1_783_886_668
        assert r["migration_slot"] == 432_499_503

    def test_sr03_zero_match_fails_closed(self):
        tx = _tx(["CFG", "OTHER"])
        infos = {"CFG": _config_acct(), "OTHER": _foreign_acct()}
        r = resolve_pumpswap_pool_from_transaction(tx, infos, expected_mint=_MINT)
        assert r["resolved"] is False
        assert r["reason"] == "no_confirmed_pumpswap_pool_in_transaction"

    def test_sr04_ambiguous_fails_closed(self):
        tx = _tx(["POOL1"], writable=["POOL2"])
        infos = {"POOL1": _pool_acct(), "POOL2": _pool_acct()}
        r = resolve_pumpswap_pool_from_transaction(tx, infos, expected_mint=_MINT)
        assert r["resolved"] is False
        assert r["reason"] == "ambiguous_multiple_pumpswap_pools"
        assert r["mint_matched_count"] == 2

    def test_sr05_missing_transaction_fails_closed(self):
        r = resolve_pumpswap_pool_from_transaction(None, {}, expected_mint=_MINT)
        assert r["resolved"] is False
        assert r["reason"] == "transaction_not_found"

    def test_sr06_config_account_excluded(self):
        tx = _tx(["CFG", "POOL"])
        infos = {"CFG": _config_acct(), "POOL": _pool_acct()}
        r = resolve_pumpswap_pool_from_transaction(tx, infos, expected_mint=_MINT)
        assert r["resolved"] is True
        assert r["pool_address"] == "POOL"
        assert r["program_owned_count"] == 2
        assert r["mint_matched_count"] == 1


class TestResolverTransport:
    def _mock(self, monkeypatch, tx_result, values_by_key):
        def fake_rpc(rpc_url, method, params, *, timeout_seconds):
            if method == "getTransaction":
                return {"result": tx_result}
            if method == "getMultipleAccounts":
                chunk = params[0]
                return {"result": {"value": [values_by_key.get(k) for k in chunk]}}
            return {"result": None}
        monkeypatch.setattr(ps, "_rpc_post", fake_rpc)

    def test_sr07_transport_end_to_end(self, monkeypatch):
        tx = _tx(["POOL", "CFG"], readonly=["LR"])
        vals = {"POOL": _pool_acct(), "CFG": _config_acct(), "LR": _foreign_acct()}
        self._mock(monkeypatch, tx, vals)
        transport = build_pumpswap_signature_pool_resolver_transport(migration_signature=_SIG, expected_mint=_MINT)
        payload = transport(None)
        result = normalize_pumpswap_confirmation_payload(dict(payload), request_kind="pumpswap_signature_pool_resolution")
        assert result.source_status == SourceStatus.COMPLETE
        tok = result.normalized_payload["tokens"][0]
        assert tok["mint"] == _MINT
        assert tok["pairAddress"] == "POOL"
        assert tok["pumpswap_confirmed"] is True
        assert tok["pumpswap_pool_resolved_from_signature"] is True
        assert tok["pumpswap_migration_block_time"] == 1_783_886_668
        assert "token_created_at" not in tok

    def test_sr08_transport_tx_not_found_fails_closed(self, monkeypatch):
        self._mock(monkeypatch, None, {})
        transport = build_pumpswap_signature_pool_resolver_transport(migration_signature=_SIG, expected_mint=_MINT)
        payload = transport(None)
        result = normalize_pumpswap_confirmation_payload(dict(payload), request_kind="pumpswap_signature_pool_resolution")
        assert result.source_status == SourceStatus.FAILED
        assert "not_found" in result.failure_type

    def test_sr09_transport_ambiguous_fails_closed(self, monkeypatch):
        tx = _tx(["POOL1", "POOL2"])
        vals = {"POOL1": _pool_acct(), "POOL2": _pool_acct()}
        self._mock(monkeypatch, tx, vals)
        transport = build_pumpswap_signature_pool_resolver_transport(migration_signature=_SIG, expected_mint=_MINT)
        payload = transport(None)
        result = normalize_pumpswap_confirmation_payload(dict(payload), request_kind="pumpswap_signature_pool_resolution")
        assert result.source_status == SourceStatus.FAILED
        assert "ambiguous" in result.failure_type


class TestNormalizeAndWiring:
    def test_sr10_resolution_provenance_no_token_created_at(self, monkeypatch):
        tx = _tx(["POOL"])
        vals = {"POOL": _pool_acct()}
        def fake_rpc(rpc_url, method, params, *, timeout_seconds):
            if method == "getTransaction":
                return {"result": tx}
            return {"result": {"value": [vals.get(k) for k in params[0]]}}
        monkeypatch.setattr(ps, "_rpc_post", fake_rpc)
        transport = build_pumpswap_signature_pool_resolver_transport(migration_signature=_SIG, expected_mint=_MINT)
        result = normalize_pumpswap_payload(dict(transport(None)), request_kind="pumpswap_signature_pool_resolution")
        assert result.source_status == SourceStatus.COMPLETE
        assert result.normalized_payload["pumpswap_resolution"]["resolved"] is True
        tok = result.normalized_payload["tokens"][0]
        assert "token_created_at" not in tok
        assert "token_age_evidence_tier" not in tok

    def test_sr11_registry_and_routing(self):
        from printer_v1.sources import SOURCE_REGISTRY
        assert "pumpswap_signature_pool_resolution" in SOURCE_REGISTRY["pumpswap"].allowed_request_kinds

    def test_sr12_no_score_fields_and_no_dexscreener_import(self):
        conf = {"confirmed": True, "expected_mint": _MINT, "pool_address": "POOL",
                "program_id": PUMPSWAP_AMM_PROGRAM_ID, "owner": PUMPSWAP_AMM_PROGRAM_ID, "base_mint_offset": 43}
        res = {"resolved": True, "account_keys_total": 5, "program_owned_count": 2, "mint_matched_count": 1}
        result = normalize_pumpswap_confirmation_payload(
            {"pumpswap_confirmation": conf, "pumpswap_resolution": res}, request_kind="pumpswap_signature_pool_resolution"
        )
        blob = repr(result.normalized_payload).lower()
        for banned in ("score", "rank", "confidence", "weight", "probability"):
            assert banned not in blob
        # The resolver must not depend on the DexScreener module (no import/call).
        pumpswap_src = (SRC_PATH / "printer_v1" / "sources" / "pumpswap.py").read_text(encoding="utf-8")
        assert "from printer_v1.sources.dexscreener" not in pumpswap_src
        assert "import dexscreener" not in pumpswap_src
        assert "dexscreener." not in pumpswap_src
