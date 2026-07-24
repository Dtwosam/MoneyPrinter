"""V2-9.7E.42 direct Pump migration discovery and graduated-candidate supply.

Proves the direct migration channel end-to-end on fixtures + isolated temporary
DBs only (no live network, no persistent-DB mutation, no lifecycle/pilot/memory):

  DM-01  PumpPortal migration normalizer carries the migration signature (locator)
  DM-02  PumpPortal alone cannot prove graduation (intake is locator only)
  DM-03  intake requires exact mint AND signature; dedup + conflict recorded
  DM-04  exact Pump migration proof: success + mint + pump prog + pumpswap prog
  DM-05  proof fails closed: no tx, failed tx, mint not referenced, prog absent
  DM-06  full verification: wrong owner / mint mismatch / zero / multiple pools
  DM-07  one valid pool -> PUMPSWAP_GRADUATED_CONFIRMED persisted end-to-end
  DM-08  migration time never becomes token_created_at (no such column/field)
  DM-09  duplicate migration events are idempotent
  DM-10  confirmed candidates persist and refresh across cycles
  DM-11  fresh (LATEST_GRADUATED) vs persisted (PERSISTED_GRADUATED) stay distinct
  DM-12  ungraduated origin-only pool export stays empty (never selectable)
  DM-13  export_graduated_pilot_candidates reads the graduated registry
  DM-14  graduation evidence immutable; delete blocked; replay deterministic
  DM-15  integrity, foreign keys, forbidden-capability deltas all zero
"""

from __future__ import annotations

import base64
import pathlib
import sqlite3
import sys
import tempfile

import pytest

PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC_PATH = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_PATH))

from printer_v1.db.migrate import apply_migrations
from printer_v1.discovery import direct_migration_discovery as dmd
from printer_v1.operator_cli.persistent_candidate_pool import (
    export_graduated_pilot_candidates,
)
from printer_v1.sources import pump_migration as pm
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pump_migration import (
    build_graduation_verifier_transport,
    prove_pump_migration_transaction,
    verify_graduation_from_transaction,
)
from printer_v1.sources.pumpportal import normalize_pumpportal_payload
from printer_v1.sources.pumpswap import (
    PUMPSWAP_AMM_PROGRAM_ID,
    _b58decode,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    GRADUATED_LIFECYCLE,
    GraduatedCandidateError,
    export_graduated_candidates,
    import_graduated_candidate_row,
    lookup_graduated_candidate,
    record_graduated_candidate,
)

_MINT_A = "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump"
_MINT_B = "GwZvGvVzjWTL1mvpw55KQWztTQvWo3B6ew16N2aspump"
_SIG_A = "ijqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESaaaaaaa"
_SIG_B = "kbqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESbbbbbbb"
_POOL_A = "6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak"
_POOL_B = "9ZgTJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhAK"
_NOW = "2026-07-23T18:00:00+00:00"


# --------------------------------------------------------------------------- #
# Synthetic on-chain fixtures                                                  #
# --------------------------------------------------------------------------- #

def _pool_acct(mint):
    data = b"\x01" * 43 + _b58decode(mint) + b"\x02" * 226
    return {"owner": PUMPSWAP_AMM_PROGRAM_ID, "data": [base64.b64encode(data).decode(), "base64"]}


def _wrong_owner_pool(mint):
    data = b"\x01" * 43 + _b58decode(mint) + b"\x02" * 226
    return {"owner": "11111111111111111111111111111111", "data": [base64.b64encode(data).decode(), "base64"]}


def _migration_tx(pool_key, mint, *, include_pump=True, include_pumpswap=True,
                  err=None, block_time=1_783_886_668, slot=432_499_503):
    static = [pool_key, mint]
    if include_pump:
        static.append(PUMP_PROGRAM_ID)
    if include_pumpswap:
        static.append(PUMPSWAP_AMM_PROGRAM_ID)
    return {
        "blockTime": block_time,
        "slot": slot,
        "transaction": {"message": {"accountKeys": static}},
        "meta": {"err": err, "loadedAddresses": {"writable": [], "readonly": []}},
    }


def _mock_rpc(monkeypatch, by_sig):
    """Patch pump_migration._rpc_post to serve tx + accounts keyed by signature."""
    def fake_rpc(rpc_url, method, params, *, timeout_seconds):
        if method == "getTransaction":
            sig = params[0]
            tx, _infos = by_sig.get(sig, (None, {}))
            return {"result": tx}
        if method == "getMultipleAccounts":
            chunk = params[0]
            # Find which signature owns these keys.
            for _sig, (_tx, infos) in by_sig.items():
                if any(k in infos for k in chunk):
                    return {"result": {"value": [infos.get(k) for k in chunk]}}
            return {"result": {"value": [None for _ in chunk]}}
        return {"result": None}
    monkeypatch.setattr(pm, "_rpc_post", fake_rpc)


def _live_verifier_factory(monkeypatch, by_sig):
    _mock_rpc(monkeypatch, by_sig)

    def factory(mint, signature):
        return build_graduation_verifier_transport(
            migration_signature=signature, expected_mint=mint
        )
    return factory


def _migration_transport(events):
    def transport(context):
        return {"events": events, "subscription_method": "subscribeMigration"}
    return transport


def _temp_db():
    fd = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    fd.close()
    apply_migrations(fd.name)
    return fd.name


def _graduated_case(mint, sig, pool):
    tx = _migration_tx(pool, mint)
    infos = {pool: _pool_acct(mint)}
    return sig, (tx, infos)


# --------------------------------------------------------------------------- #
# DM-01 / DM-02 / DM-03 — intake & locator                                    #
# --------------------------------------------------------------------------- #

class TestIntake:
    def test_dm01_normalizer_carries_migration_signature(self):
        payload = {"events": [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]}
        result = normalize_pumpportal_payload(payload, request_kind="pumpfun_migration_stream")
        token = result.normalized_payload["tokens"][0]
        assert token["migration_signature"] == _SIG_A
        # locator only — no token creation time ever from a migration event.
        assert token["token_created_at"] is None

    def test_dm02_pumpportal_alone_is_locator_only(self):
        payload = {"events": [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]}
        result = normalize_pumpportal_payload(payload, request_kind="pumpfun_migration_stream")
        intake = dmd.intake_migration_events(result.normalized_payload)
        # The event yields a locator pair, not a graduation proof or persistence.
        assert intake["valid_pair_count"] == 1
        assert intake["valid_pairs"][0] == {"mint": _MINT_A, "signature": _SIG_A}

    def test_dm03_requires_mint_and_signature_dedup_and_conflict(self):
        payload = {
            "tokens": [
                {"chain": "solana", "mint": _MINT_A, "migration_signature": _SIG_A},   # valid
                {"chain": "solana", "mint": _MINT_A, "migration_signature": _SIG_A},   # duplicate
                {"chain": "solana", "mint": _MINT_B, "migration_signature": None},     # missing sig
                {"chain": "solana", "mint": "", "migration_signature": _SIG_B},        # missing mint
                {"chain": "solana", "mint": _MINT_A, "migration_signature": _SIG_B},   # mint->2 sigs
                {"chain": "solana", "mint": _MINT_B, "migration_signature": _SIG_A},   # sig->2 mints
            ]
        }
        intake = dmd.intake_migration_events(payload)
        assert intake["valid_pair_count"] == 1
        assert intake["duplicate"] == 1
        assert intake["missing_signature"] == 1
        assert intake["missing_mint"] == 1
        assert intake["conflicting_count"] == 2


# --------------------------------------------------------------------------- #
# DM-04 / DM-05 — exact Pump migration proof                                  #
# --------------------------------------------------------------------------- #

class TestPumpMigrationProof:
    def test_dm04_valid_proof(self):
        tx = _migration_tx(_POOL_A, _MINT_A)
        proof = prove_pump_migration_transaction(tx, expected_mint=_MINT_A)
        assert proof["proven"] is True
        assert proof["reason"] == "proven_pump_migration"
        assert proof["migration_block_time"] == 1_783_886_668
        assert proof["migration_slot"] == 432_499_503

    def test_dm05_no_transaction(self):
        proof = prove_pump_migration_transaction(None, expected_mint=_MINT_A)
        assert proof["proven"] is False
        assert proof["reason"] == "migration_transaction_not_found"

    def test_dm05_failed_transaction(self):
        tx = _migration_tx(_POOL_A, _MINT_A, err={"InstructionError": [0, "X"]})
        proof = prove_pump_migration_transaction(tx, expected_mint=_MINT_A)
        assert proof["proven"] is False
        assert proof["reason"] == "migration_transaction_failed"

    def test_dm05_mint_not_referenced(self):
        tx = _migration_tx(_POOL_A, _MINT_A)
        proof = prove_pump_migration_transaction(tx, expected_mint=_MINT_B)
        assert proof["proven"] is False
        assert proof["reason"] == "mint_not_referenced"

    def test_dm05_pump_program_absent(self):
        tx = _migration_tx(_POOL_A, _MINT_A, include_pump=False)
        proof = prove_pump_migration_transaction(tx, expected_mint=_MINT_A)
        assert proof["proven"] is False
        assert proof["reason"] == "pump_program_not_present"

    def test_dm05_pumpswap_program_absent(self):
        tx = _migration_tx(_POOL_A, _MINT_A, include_pumpswap=False)
        proof = prove_pump_migration_transaction(tx, expected_mint=_MINT_A)
        assert proof["proven"] is False
        assert proof["reason"] == "pumpswap_program_not_invoked"

    def test_dm05_future_block_time(self):
        tx = _migration_tx(_POOL_A, _MINT_A, block_time=2_000_000_000)
        proof = prove_pump_migration_transaction(tx, expected_mint=_MINT_A, now_epoch=1_783_886_668)
        assert proof["proven"] is False
        assert proof["reason"] == "migration_block_time_in_future"


# --------------------------------------------------------------------------- #
# DM-06 — full verification fail-closed matrix                                #
# --------------------------------------------------------------------------- #

class TestFullVerification:
    def test_dm06_valid_end_to_end(self):
        tx = _migration_tx(_POOL_A, _MINT_A)
        infos = {_POOL_A: _pool_acct(_MINT_A)}
        v = verify_graduation_from_transaction(tx, infos, expected_mint=_MINT_A)
        assert v["verified"] is True
        assert v["pool_address"] == _POOL_A
        assert v["migration_block_time"] == 1_783_886_668

    def test_dm06_wrong_owner_fails(self):
        tx = _migration_tx(_POOL_A, _MINT_A)
        infos = {_POOL_A: _wrong_owner_pool(_MINT_A)}
        v = verify_graduation_from_transaction(tx, infos, expected_mint=_MINT_A)
        assert v["verified"] is False
        assert v["stage"] == "POOL_RESOLUTION"

    def test_dm06_mint_mismatch_fails(self):
        # pool actually encodes MINT_B while candidate mint is MINT_A.
        tx = _migration_tx(_POOL_A, _MINT_A)
        infos = {_POOL_A: _pool_acct(_MINT_B)}
        v = verify_graduation_from_transaction(tx, infos, expected_mint=_MINT_A)
        assert v["verified"] is False
        assert v["stage"] == "POOL_RESOLUTION"

    def test_dm06_zero_pool_fails(self):
        tx = _migration_tx(_POOL_A, _MINT_A)
        infos = {_POOL_A: None}
        v = verify_graduation_from_transaction(tx, infos, expected_mint=_MINT_A)
        assert v["verified"] is False
        assert v["stage"] == "POOL_RESOLUTION"
        assert v["reason"] == "no_confirmed_pumpswap_pool_in_transaction"

    def test_dm06_multiple_pools_fails(self):
        tx = {
            "blockTime": 1_783_886_668, "slot": 1,
            "transaction": {"message": {"accountKeys": [
                _POOL_A, _POOL_B, _MINT_A, PUMP_PROGRAM_ID, PUMPSWAP_AMM_PROGRAM_ID]}},
            "meta": {"err": None, "loadedAddresses": {"writable": [], "readonly": []}},
        }
        infos = {_POOL_A: _pool_acct(_MINT_A), _POOL_B: _pool_acct(_MINT_A)}
        v = verify_graduation_from_transaction(tx, infos, expected_mint=_MINT_A)
        assert v["verified"] is False
        assert v["reason"] == "ambiguous_multiple_pumpswap_pools"


# --------------------------------------------------------------------------- #
# DM-07 .. DM-15 — orchestrator, persistence, mix, integrity                  #
# --------------------------------------------------------------------------- #

class TestOrchestratorAndPersistence:
    def test_dm07_valid_event_reaches_confirmed_persistence(self, monkeypatch):
        db = _temp_db()
        by_sig = dict([_graduated_case(_MINT_A, _SIG_A, _POOL_A)])
        report = dmd.run_direct_migration_discovery(
            db,
            migration_transport=_migration_transport(
                [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]
            ),
            verifier_transport_factory=_live_verifier_factory(monkeypatch, by_sig),
            now=_NOW,
        )
        assert report["confirmed_count"] == 1
        assert report["verifications"][0]["verified"] is True
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = lookup_graduated_candidate(conn, _MINT_A)
        assert row["lifecycle_state"] == GRADUATED_LIFECYCLE
        assert row["pumpswap_pool"] == _POOL_A
        assert row["market_identity"] == f"solana-mainnet:pumpswap:{_POOL_A}"
        conn.close()

    def test_dm08_no_token_created_at_column_or_field(self):
        db = _temp_db()
        conn = sqlite3.connect(db)
        cols = [r[1] for r in conn.execute(
            "PRAGMA table_info(printer_pumpswap_graduated_candidate_registry)"
        ).fetchall()]
        conn.close()
        assert "token_created_at" not in cols
        assert "token_age_seconds" not in cols
        assert any(c == "graduation_block_time" for c in cols)

    def test_dm09_duplicate_events_idempotent(self, monkeypatch):
        db = _temp_db()
        by_sig = dict([_graduated_case(_MINT_A, _SIG_A, _POOL_A)])
        factory = _live_verifier_factory(monkeypatch, by_sig)
        events = [
            {"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A},
            {"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A},
        ]
        report = dmd.run_direct_migration_discovery(
            db, migration_transport=_migration_transport(events),
            verifier_transport_factory=factory, now=_NOW,
        )
        # Duplicate collapsed at intake; exactly one persisted candidate.
        assert report["migration_intake"]["duplicate"] == 1
        assert report["source_operation_ledger"]["graduated_candidates"] == 1

    def test_dm10_persist_and_refresh_across_cycles(self, monkeypatch):
        db = _temp_db()
        by_sig = dict([_graduated_case(_MINT_A, _SIG_A, _POOL_A)])
        factory = _live_verifier_factory(monkeypatch, by_sig)
        events = [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]
        dmd.run_direct_migration_discovery(
            db, migration_transport=_migration_transport(events),
            verifier_transport_factory=factory, now=_NOW,
        )
        # Second cycle re-observes the same graduation -> idempotent refresh.
        dmd.run_direct_migration_discovery(
            db, migration_transport=_migration_transport(events),
            verifier_transport_factory=factory, now="2026-07-23T18:05:00+00:00",
        )
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        row = lookup_graduated_candidate(conn, _MINT_A)
        assert int(row["observation_count"]) == 2
        assert row["latest_observed_at"] == "2026-07-23T18:05:00+00:00"
        conn.close()

    def test_dm11_fresh_vs_persisted_categories_distinct(self, monkeypatch):
        db = _temp_db()
        # Cycle 1: confirm A (persisted).
        by_sig_a = dict([_graduated_case(_MINT_A, _SIG_A, _POOL_A)])
        dmd.run_direct_migration_discovery(
            db, migration_transport=_migration_transport(
                [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]),
            verifier_transport_factory=_live_verifier_factory(monkeypatch, by_sig_a),
            now=_NOW,
        )
        # Cycle 2: confirm B fresh; A becomes persisted (not re-observed).
        by_sig_b = dict([_graduated_case(_MINT_B, _SIG_B, _POOL_B)])
        report = dmd.run_direct_migration_discovery(
            db, migration_transport=_migration_transport(
                [{"mint": _MINT_B, "signature": _SIG_B, "newRaydiumPool": _POOL_B}]),
            verifier_transport_factory=_live_verifier_factory(monkeypatch, by_sig_b),
            now="2026-07-23T18:05:00+00:00",
        )
        cats = {m["mint"]: m["category"] for m in report["candidate_mix"]}
        assert cats[_MINT_B] == "LATEST_GRADUATED"
        # V2-9.7E.43: truthful persisted-graduated provenance (was PERSISTED_ACTIVE).
        assert cats[_MINT_A] == "PERSISTED_GRADUATED"
        assert report["latest_graduated_count"] == 1
        assert report["persisted_graduated_count"] == 1

    def test_dm12_origin_only_pool_export_empty(self):
        db = _temp_db()
        # No graduated rows -> honest empty export (never selectable).
        result = export_graduated_pilot_candidates(db)
        assert result["exported"] == 0
        assert result["graduated_candidates"] == []
        assert result["reason"] == "NO_PERSISTED_GRADUATION_EVIDENCE"

    def test_dm13_export_reads_graduated_registry(self):
        db = _temp_db()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        record_graduated_candidate(
            conn, mint=_MINT_A, migration_signature=_SIG_A, pumpswap_pool=_POOL_A,
            graduation_block_time=1_783_886_668, graduation_slot=1, now=_NOW,
        )
        conn.commit()
        conn.close()
        result = export_graduated_pilot_candidates(db)
        assert result["exported"] == 1
        assert result["reason"] == "GRADUATED_EVIDENCE_EXPORTED"
        assert result["graduated_candidates"][0]["mint_identity"] == _MINT_A

    def test_dm14_evidence_immutable_and_conflict(self):
        db = _temp_db()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        record_graduated_candidate(
            conn, mint=_MINT_A, migration_signature=_SIG_A, pumpswap_pool=_POOL_A,
            graduation_block_time=1_783_886_668, graduation_slot=1, now=_NOW,
        )
        conn.commit()
        # Immutable evidence: cannot change the pool.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE printer_pumpswap_graduated_candidate_registry "
                "SET pumpswap_pool=? WHERE mint_identity=?", (_POOL_B, _MINT_A))
        # Immutable: cannot delete.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "DELETE FROM printer_pumpswap_graduated_candidate_registry "
                "WHERE mint_identity=?", (_MINT_A,))
        conn.rollback()
        # Conflicting graduation evidence for a known mint fails closed.
        with pytest.raises(GraduatedCandidateError):
            record_graduated_candidate(
                conn, mint=_MINT_A, migration_signature=_SIG_B, pumpswap_pool=_POOL_B,
                graduation_block_time=1_783_886_669, graduation_slot=2, now=_NOW,
            )
        conn.close()

    def test_dm14_replay_idempotent_import(self):
        db = _temp_db()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        record_graduated_candidate(
            conn, mint=_MINT_A, migration_signature=_SIG_A, pumpswap_pool=_POOL_A,
            graduation_block_time=1_783_886_668, graduation_slot=1, now=_NOW,
        )
        conn.commit()
        exported = export_graduated_candidates(conn)
        # Fresh DB, verbatim import is idempotent for a byte-identical row.
        db2 = _temp_db()
        conn2 = sqlite3.connect(db2)
        conn2.row_factory = sqlite3.Row
        assert import_graduated_candidate_row(conn2, exported[0]) is True
        assert import_graduated_candidate_row(conn2, exported[0]) is False
        conn2.commit()
        conn.close()
        conn2.close()

    def test_dm15_integrity_and_forbidden_deltas_zero(self, monkeypatch):
        db = _temp_db()
        by_sig = dict([_graduated_case(_MINT_A, _SIG_A, _POOL_A)])
        report = dmd.run_direct_migration_discovery(
            db, migration_transport=_migration_transport(
                [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]),
            verifier_transport_factory=_live_verifier_factory(monkeypatch, by_sig),
            now=_NOW,
        )
        assert report["forbidden_delta_total"] == 0
        # Source ledger recorded governed migration + verify requests.
        assert report["source_operation_ledger"]["source_requests"] >= 2
        assert report["source_operation_ledger"]["source_responses"] >= 2
        conn = sqlite3.connect(db)
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        conn.close()

    def test_dm06_failed_verification_not_persisted(self, monkeypatch):
        db = _temp_db()
        # Zero-pool case: verification fails closed, nothing persisted.
        tx = _migration_tx(_POOL_A, _MINT_A)
        by_sig = {_SIG_A: (tx, {_POOL_A: None})}
        report = dmd.run_direct_migration_discovery(
            db, migration_transport=_migration_transport(
                [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]),
            verifier_transport_factory=_live_verifier_factory(monkeypatch, by_sig),
            now=_NOW,
        )
        assert report["confirmed_count"] == 0
        assert report["verifications"][0]["verified"] is False
        assert report["source_operation_ledger"]["graduated_candidates"] == 0


class TestBL4201Robustness:
    """BL-42-01: transient not-yet-finalized transactions re-verify; non-transient
    failures never retry; multi-round collection accumulates and deduplicates."""

    def test_transient_failure_reverifies_and_confirms(self):
        db = _temp_db()
        pool_acct = _pool_acct(_MINT_A)
        tx = _migration_tx(_POOL_A, _MINT_A)
        calls = {"n": 0}

        def factory(mint, signature):
            def transport(context):
                calls["n"] += 1
                if calls["n"] == 1:
                    # First attempt: transaction not yet queryable (transient).
                    return {
                        "fixture_status": "failure",
                        "failure_type": "pumpswap_rpc_transport_error",
                        "failure_message": "timeout",
                    }
                # Second attempt after settle: confirmed.
                from printer_v1.sources.pump_migration import verify_graduation_from_transaction
                v = verify_graduation_from_transaction(tx, {_POOL_A: pool_acct}, expected_mint=mint)
                return {
                    "pumpswap_confirmation": v["pumpswap_confirmation"],
                    "pumpswap_resolution": v["pumpswap_resolution"],
                    "migration_signature": signature,
                    "migration_block_time": v["migration_block_time"],
                    "migration_slot": v["migration_slot"],
                }
            return transport

        report = dmd.run_direct_migration_discovery(
            db,
            migration_transport=_migration_transport(
                [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]
            ),
            verifier_transport_factory=factory,
            now=_NOW,
            reverify_on_transient=True,
        )
        assert report["confirmed_count"] == 1
        assert report["verifications"][0]["verify_attempts"] == 2
        assert calls["n"] == 2

    def test_non_transient_failure_not_retried(self):
        db = _temp_db()
        calls = {"n": 0}

        def factory(mint, signature):
            def transport(context):
                calls["n"] += 1
                # Non-transient: a genuine graduation failure (wrong owner).
                return {
                    "fixture_status": "failure",
                    "failure_type": "graduation_verification_failed_pool_resolution_pool_owner_not_pumpswap_program",
                    "failure_message": "wrong owner",
                }
            return transport

        report = dmd.run_direct_migration_discovery(
            db,
            migration_transport=_migration_transport(
                [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]
            ),
            verifier_transport_factory=factory,
            now=_NOW,
            reverify_on_transient=True,
        )
        assert report["confirmed_count"] == 0
        assert report["verifications"][0]["verify_attempts"] == 1
        assert calls["n"] == 1

    def test_multi_round_collection_accumulates_and_dedups(self, monkeypatch):
        db = _temp_db()
        by_sig = dict([
            _graduated_case(_MINT_A, _SIG_A, _POOL_A),
            _graduated_case(_MINT_B, _SIG_B, _POOL_B),
        ])
        factory = _live_verifier_factory(monkeypatch, by_sig)
        rounds = {"n": 0}

        def migration_transport(context):
            rounds["n"] += 1
            if rounds["n"] == 1:
                return {"events": [{"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A}]}
            # Round 2 re-sees A (duplicate across rounds) and adds B.
            return {"events": [
                {"mint": _MINT_A, "signature": _SIG_A, "newRaydiumPool": _POOL_A},
                {"mint": _MINT_B, "signature": _SIG_B, "newRaydiumPool": _POOL_B},
            ]}

        report = dmd.run_direct_migration_discovery(
            db, migration_transport=migration_transport,
            verifier_transport_factory=factory, now=_NOW, collection_rounds=2,
        )
        assert report["migration_intake"]["collection_rounds"] == 2
        assert report["migration_intake"]["valid_pair_count"] == 2
        assert report["migration_intake"]["duplicate"] == 1  # A re-seen in round 2
        assert report["confirmed_count"] == 2
        assert report["source_operation_ledger"]["graduated_candidates"] == 2


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"]))
