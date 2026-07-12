"""Stage 2 — governed on-chain PumpSwap pool confirmation (read-only).

Confirms a pool account is owned by the PumpSwap AMM program and that the
expected mint is the pool's base_mint, using a Solana RPC getAccountInfo read.
Migration transaction block-time may be stored as migration evidence only and
must NEVER become token_created_at.

  PS-01  valid account -> confirmed
  PS-02  wrong owner -> rejected (program mismatch)
  PS-03  wrong base_mint -> rejected (mint mismatch)
  PS-04  missing account -> rejected
  PS-05  undecodable / short data -> rejected
  PS-06  normalize confirmed payload -> COMPLETE, no token_created_at
  PS-07  normalize unconfirmed payload -> FAILED (fails closed)
  PS-08  request-kind routing via normalize_pumpswap_payload
  PS-09  migration block-time stored as migration evidence, never token_created_at
  PS-10  transport (mocked RPC) confirms end-to-end incl getTransaction block-time
  PS-11  transport mismatch/duplicate fail closed
  PS-12  program ID + registry wiring; no score/rank fields

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

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources import pumpswap as ps
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _PUMPSWAP_POOL_BASE_MINT_OFFSET,
    _b58decode,
    build_pumpswap_confirmation_transport,
    confirm_pumpswap_pool_from_account,
    normalize_pumpswap_confirmation_payload,
    normalize_pumpswap_payload,
)

_MINT = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
_POOL = "DfxsEZga7jwVhwo6JUfWnDD8tg9aSLcv32UYzLQ3SwqD"
_SIG = "ijqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usES3Zx5QMs"
_OTHER_MINT = "So11111111111111111111111111111111111111112"


def _pool_account(owner=PUMPSWAP_AMM_PROGRAM_ID, mint=_MINT, total_len=301):
    mb = _b58decode(mint)
    off = _PUMPSWAP_POOL_BASE_MINT_OFFSET
    data = b"\x01" * off + mb + b"\x02" * (total_len - off - len(mb))
    return {"owner": owner, "data": [base64.b64encode(data).decode(), "base64"]}


class TestConfirmCore:
    def test_ps01_valid_confirmed(self):
        r = confirm_pumpswap_pool_from_account(_pool_account(), expected_mint=_MINT, pool_address=_POOL)
        assert r["confirmed"] is True
        assert r["reason"] == "confirmed_pumpswap_pool"
        assert r["owner"] == PUMPSWAP_AMM_PROGRAM_ID
        assert r["base_mint"] == _MINT

    def test_ps02_wrong_owner_rejected(self):
        acct = _pool_account(owner="Raydium1111111111111111111111111111111111111")
        r = confirm_pumpswap_pool_from_account(acct, expected_mint=_MINT, pool_address=_POOL)
        assert r["confirmed"] is False
        assert r["reason"] == "pool_owner_not_pumpswap_program"

    def test_ps03_mint_mismatch_rejected(self):
        r = confirm_pumpswap_pool_from_account(_pool_account(mint=_MINT), expected_mint=_OTHER_MINT, pool_address=_POOL)
        assert r["confirmed"] is False
        assert r["reason"] == "base_mint_mismatch"

    def test_ps04_missing_account_rejected(self):
        r = confirm_pumpswap_pool_from_account(None, expected_mint=_MINT, pool_address=_POOL)
        assert r["confirmed"] is False
        assert r["reason"] == "pool_account_not_found"

    def test_ps05_short_data_rejected(self):
        acct = {"owner": PUMPSWAP_AMM_PROGRAM_ID, "data": [base64.b64encode(b"\x00" * 10).decode(), "base64"]}
        r = confirm_pumpswap_pool_from_account(acct, expected_mint=_MINT, pool_address=_POOL)
        assert r["confirmed"] is False
        assert r["reason"] == "pool_account_data_too_short"


class TestNormalizeConfirmation:
    def _confirmed_payload(self, block_time=1_783_886_668):
        conf = confirm_pumpswap_pool_from_account(_pool_account(), expected_mint=_MINT, pool_address=_POOL)
        return {
            "pumpswap_confirmation": conf,
            "migration_signature": _SIG,
            "migration_block_time": block_time,
            "migration_slot": 432_499_503,
        }

    def test_ps06_confirmed_complete_no_token_created_at(self):
        result = normalize_pumpswap_confirmation_payload(self._confirmed_payload(), request_kind="pumpswap_onchain_pool_confirmation")
        assert result.source_status == SourceStatus.COMPLETE
        assert result.data_quality_label == DataQualityLabel.CLEAN_DATA
        tok = result.normalized_payload["tokens"][0]
        assert tok["mint"] == _MINT
        assert tok["pairAddress"] == _POOL
        assert tok["dex"] == "pumpswap"
        assert tok["pumpswap_confirmed"] is True
        assert tok["pumpswap_program_id"] == PUMPSWAP_AMM_PROGRAM_ID
        # Critical: no token creation time is ever stamped by confirmation.
        assert "token_created_at" not in tok
        assert tok.get("token_age_seconds") is None if "token_age_seconds" in tok else True

    def test_ps07_unconfirmed_fails_closed(self):
        conf = confirm_pumpswap_pool_from_account(
            _pool_account(owner="X1111111111111111111111111111111111111111111"),
            expected_mint=_MINT, pool_address=_POOL,
        )
        result = normalize_pumpswap_confirmation_payload(
            {"pumpswap_confirmation": conf}, request_kind="pumpswap_onchain_pool_confirmation"
        )
        assert result.source_status == SourceStatus.FAILED
        assert "pool_owner_not_pumpswap_program" in result.failure_type

    def test_ps08_request_kind_routing(self):
        result = normalize_pumpswap_payload(self._confirmed_payload(), request_kind="pumpswap_onchain_pool_confirmation")
        assert result.source_status == SourceStatus.COMPLETE
        assert result.normalized_payload["tokens"][0]["pumpswap_confirmed"] is True

    def test_ps09_migration_block_time_is_evidence_only(self):
        result = normalize_pumpswap_confirmation_payload(self._confirmed_payload(), request_kind="pumpswap_onchain_pool_confirmation")
        tok = result.normalized_payload["tokens"][0]
        assert tok["pumpswap_migration_block_time"] == 1_783_886_668
        assert tok["pumpswap_migration_signature"] == _SIG
        # Migration time must not leak into any token-age field.
        assert "token_created_at" not in tok
        assert "token_age_evidence_tier" not in tok


class TestConfirmationTransport:
    def _mock_rpc(self, monkeypatch, account_value, block_time=1_783_886_668):
        def fake_rpc(rpc_url, method, params, *, timeout_seconds):
            if method == "getAccountInfo":
                return {"result": {"value": account_value}}
            if method == "getTransaction":
                return {"result": {"blockTime": block_time, "slot": 432_499_503}}
            return {"result": None}
        monkeypatch.setattr(ps, "_rpc_post", fake_rpc)

    def test_ps10_transport_confirms_end_to_end(self, monkeypatch):
        self._mock_rpc(monkeypatch, _pool_account())
        transport = build_pumpswap_confirmation_transport(
            expected_mint=_MINT, pool_address=_POOL, migration_signature=_SIG
        )
        payload = transport(None)
        result = normalize_pumpswap_confirmation_payload(dict(payload), request_kind="pumpswap_onchain_pool_confirmation")
        assert result.source_status == SourceStatus.COMPLETE
        tok = result.normalized_payload["tokens"][0]
        assert tok["pumpswap_confirmed"] is True
        assert tok["pumpswap_migration_block_time"] == 1_783_886_668
        assert "token_created_at" not in tok

    def test_ps11_transport_mismatch_fails_closed(self, monkeypatch):
        self._mock_rpc(monkeypatch, _pool_account(owner="NotPumpSwap111111111111111111111111111111111"))
        transport = build_pumpswap_confirmation_transport(expected_mint=_MINT, pool_address=_POOL)
        payload = transport(None)
        result = normalize_pumpswap_confirmation_payload(dict(payload), request_kind="pumpswap_onchain_pool_confirmation")
        assert result.source_status == SourceStatus.FAILED


class TestWiring:
    def test_ps12_program_id_and_registry(self):
        from printer_v1.sources import SOURCE_REGISTRY
        assert PUMPSWAP_AMM_PROGRAM_ID == "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
        assert "pumpswap_onchain_pool_confirmation" in SOURCE_REGISTRY["pumpswap"].allowed_request_kinds

    def test_ps12b_no_score_or_rank_fields(self):
        conf = confirm_pumpswap_pool_from_account(_pool_account(), expected_mint=_MINT, pool_address=_POOL)
        result = normalize_pumpswap_confirmation_payload(
            {"pumpswap_confirmation": conf}, request_kind="pumpswap_onchain_pool_confirmation"
        )
        blob = repr(result.normalized_payload).lower()
        for banned in ("score", "rank", "confidence", "weight", "probability"):
            assert banned not in blob
