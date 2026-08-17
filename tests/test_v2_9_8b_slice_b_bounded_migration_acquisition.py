"""V2-9.8B Slice B: bounded migration-targeted canonical acquisition.

Proves the direct canonical Pump migration feeder is repaired without
PumpPortal, without a paid provider, and without a generic Pump-program
fallback:

    getSignaturesForAddress(PUMP_WITHDRAW_AUTHORITY_ID, finalized[, before])
      -> getTransaction(signature, finalized)
      -> exact pinned migrate / migrate_v2 decode
      -> PumpSwap canonical verification
      -> canonical graduated registry persistence
      -> contiguous durable cursor advancement

Disposable SQLite plus injected transports only. No network, no provider
contact, no authorization, no lifecycle, no memory/retrieval, no paper decision,
position, trade or PnL surface, no wallet or signing.
"""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "tests"))

from printer_v1.db import apply_migrations
from printer_v1.db.sqlite_write_contracts import connect_operational
from printer_v1.db.migrate import MIGRATIONS_DIR, canonical_migration_names
from printer_v1.discovery import direct_migration_discovery as dmd
from printer_v1.discovery.direct_migration_discovery import (
    BACKFILL_MODE,
    CONTINUITY_BLOCKED_CONTRACT,
    CONTINUITY_CONTIGUOUS,
    CONTINUITY_EXHAUSTED,
    CONTINUITY_UNINITIALIZED,
    LIVE_TAIL_MODE,
    load_direct_migration_cursor,
    run_direct_migration_discovery,
)
from printer_v1.discovery.eligible_token_supply import (
    AcquisitionQuantumKind,
    acquisition_quantum_bound,
)
from printer_v1.sources.direct_pump_migration import (
    DIRECT_MIGRATION_INDEXED_ADDRESS,
    DIRECT_PUMP_MIGRATION_CONTRACT_HASH,
    DIRECT_PUMP_MIGRATION_DECODER_VERSION,
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
    build_direct_pump_migration_transport,
)
from printer_v1.sources.pump_contracts import (
    MIGRATE_V2_DECLARED_ACCOUNT_COUNT,
    PUMP_IDL_SHA256,
    PUMP_MIGRATE_DISCRIMINATOR,
    PUMP_MIGRATE_V2_DISCRIMINATOR,
    PUMP_PROGRAM_ID,
    PUMP_WITHDRAW_AUTHORITY_ID,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    export_graduated_candidates,
)

from test_v2_9_8b_candidate_acquisition_foundation import (
    FIXTURE as ACQUISITION_FIXTURE,
    _pinned_migration_fixture,
)
from test_v2_9_8b_pump_migrate_v2_contract import _tx_from_accounts, _v2_accounts
from test_v2_9_8b_restored_factory_source_compatibility_reset import (
    _verifier_factory,
)


_NOW = "2026-08-17T12:00:00+00:00"
_COOPERATIVE_LOOKUPS = 6


def _sig(label: str) -> str:
    """Deterministic 88-character base58-ish signature identity."""
    return (label + "1" * 88)[:88]


@pytest.fixture()
def db_path(tmp_path) -> str:
    path = tmp_path / "slice-b.sqlite3"
    apply_migrations(path)
    return str(path)


# --------------------------------------------------------------------------- #
# Injected transports                                                          #
# --------------------------------------------------------------------------- #


class RecordingTransport:
    """One Solana JSON-RPC response per governed operation, fully recorded."""

    def __init__(self, pages, transactions):
        # ``pages`` maps cursor_before (or None) -> list of signature rows.
        self.pages = dict(pages)
        # ``transactions`` maps signature -> {"result": tx} or a failure payload.
        self.transactions = dict(transactions)
        self.page_payloads: list[dict] = []
        self.transaction_signatures: list[str] = []

    def __call__(self, context):
        kind = context.request.request_kind
        payload = dict(context.request.payload or {})
        if kind == SIGNATURE_PAGE_REQUEST_KIND:
            self.page_payloads.append(payload)
            assert payload["indexed_address"] == PUMP_WITHDRAW_AUTHORITY_ID
            rows = self.pages.get(payload.get("cursor_before"))
            if rows is None:
                return {
                    "fixture_status": "failure",
                    "failure_type": "direct_pump_rpc_http_error",
                    "failure_message": "no fixture page for this cursor",
                }
            return {"result": [dict(row) for row in rows[: payload["signature_limit"]]]}
        if kind == TRANSACTION_REQUEST_KIND:
            signature = str(payload.get("signature"))
            self.transaction_signatures.append(signature)
            return dict(self.transactions.get(signature) or {"result": None})
        raise AssertionError(kind)

    @property
    def page_count(self) -> int:
        return len(self.page_payloads)


def _row(signature: str, slot: int, *, err=None) -> dict:
    return {
        "signature": signature,
        "slot": slot,
        "err": err,
        "confirmationStatus": "finalized",
    }


def _non_migration_tx(slot: int) -> dict:
    """A finalized transaction with zero pinned Pump migrate instructions."""
    return {
        "result": {
            "version": 0,
            "slot": slot,
            "blockTime": 1_785_326_400,
            "transaction": {
                "message": {
                    "accountKeys": [PUMP_PROGRAM_ID, PUMP_WITHDRAW_AUTHORITY_ID],
                    "instructions": [],
                }
            },
            "meta": {
                "err": None,
                "innerInstructions": [],
                "loadedAddresses": {"writable": [], "readonly": []},
            },
        }
    }


def _source_failure_tx() -> dict:
    return {
        "fixture_status": "failure",
        "failure_type": "direct_pump_rpc_rate_limited",
        "failure_message": "Solana RPC HTTP 429",
    }


def _legacy_migration_case() -> tuple[dict, dict, str, str]:
    tx, infos, mint, pool = _pinned_migration_fixture()
    return tx, infos, mint, pool


def _migrate_v2_case() -> tuple[dict, dict, str, str]:
    mint = ACQUISITION_FIXTURE["candidates"][0][0]
    user = ACQUISITION_FIXTURE["candidates"][1][0]
    accounts, infos, pool = _v2_accounts(mint, user)
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
    return tx, infos, mint, pool


def _unsupported_contract_tx() -> dict:
    """Positive pinned migrate match the adopted contract cannot validate."""
    mint = ACQUISITION_FIXTURE["candidates"][0][0]
    user = ACQUISITION_FIXTURE["candidates"][1][0]
    accounts, _infos, _pool = _v2_accounts(mint, user)
    # Two supported migrate instructions: a positive migration match count that
    # the exactly-one contract cannot validate.
    tx = _tx_from_accounts(accounts, discriminator=PUMP_MIGRATE_V2_DISCRIMINATOR)
    instruction = tx["transaction"]["message"]["instructions"][0]
    tx["transaction"]["message"]["instructions"].append(dict(instruction))
    return {"result": tx}


def _run(
    db_path,
    transport,
    *,
    mode=LIVE_TAIL_MODE,
    verifier_factory=None,
    max_candidates=1,
    lookups=_COOPERATIVE_LOOKUPS,
    now=_NOW,
    key="slice-b",
):
    return run_direct_migration_discovery(
        db_path,
        migration_transport=transport,
        verifier_transport_factory=verifier_factory or _never_verify,
        now=now,
        request_key_prefix=key,
        max_candidates=max_candidates,
        max_transaction_lookups=lookups,
        acquisition_mode=mode,
    )


def _never_verify(mint: str, signature: str):
    def transport(context):
        raise AssertionError("PumpSwap verification must not run for this fixture")

    return transport


def _failing_verifier(mint: str, signature: str):
    def transport(context):
        return {
            "fixture_status": "failure",
            "failure_type": "pumpswap_account_batch_provider_failure",
            "failure_message": "PumpSwap account batch provider unavailable",
        }

    return transport


def _cursor(db_path):
    connection = sqlite3.connect(db_path)
    try:
        return load_direct_migration_cursor(connection)
    finally:
        connection.close()


# --------------------------------------------------------------------------- #
# B1 / B2 — migration-targeted locator                                         #
# --------------------------------------------------------------------------- #


def test_b1_signature_history_targets_the_withdraw_authority(monkeypatch) -> None:
    calls: list[tuple] = []

    def fake_post(rpc_url, method, params, *, timeout_seconds):
        calls.append((method, params))
        return {"result": []}

    monkeypatch.setattr(
        "printer_v1.sources.direct_pump_migration._rpc_post", fake_post
    )
    transport = build_direct_pump_migration_transport(
        rpc_url="https://rpc.invalid/slice-b"
    )

    class _Request:
        request_kind = SIGNATURE_PAGE_REQUEST_KIND
        payload = {
            "indexed_address": DIRECT_MIGRATION_INDEXED_ADDRESS,
            "cursor_before": None,
            "signature_limit": _COOPERATIVE_LOOKUPS,
        }

    class _Context:
        request = _Request()

    transport(_Context())

    assert len(calls) == 1
    method, params = calls[0]
    assert method == "getSignaturesForAddress"
    assert params[0] == PUMP_WITHDRAW_AUTHORITY_ID
    assert params[0] != PUMP_PROGRAM_ID
    assert DIRECT_MIGRATION_INDEXED_ADDRESS == PUMP_WITHDRAW_AUTHORITY_ID
    source = (
        ROOT / "src/printer_v1/sources/direct_pump_migration.py"
    ).read_text(encoding="utf-8")
    assert "pumpportal" not in source.lower()


def test_b2_both_migration_variants_pin_the_target_address() -> None:
    legacy_tx, _infos, _mint, _pool = _legacy_migration_case()
    legacy_keys = legacy_tx["transaction"]["message"]["accountKeys"]
    assert legacy_keys[1] == PUMP_WITHDRAW_AUTHORITY_ID

    mint = ACQUISITION_FIXTURE["candidates"][0][0]
    user = ACQUISITION_FIXTURE["candidates"][1][0]
    accounts, _v2_infos, _v2_pool = _v2_accounts(mint, user)
    assert len(accounts) == MIGRATE_V2_DECLARED_ACCOUNT_COUNT
    assert accounts[1] == PUMP_WITHDRAW_AUTHORITY_ID

    # Slice A contract truth is unchanged.
    assert PUMP_MIGRATE_DISCRIMINATOR != PUMP_MIGRATE_V2_DISCRIMINATOR


# --------------------------------------------------------------------------- #
# B3 / B4 / B5 — cursor-free live tail, exact backfill, page/coverage parity   #
# --------------------------------------------------------------------------- #


def test_b3_live_tail_carries_no_cursor(db_path) -> None:
    transport = RecordingTransport({None: []}, {})
    report = _run(db_path, transport)
    payload = transport.page_payloads[0]
    assert payload["cursor_before"] is None
    assert report["cursor_before"] is None
    assert report["cursor_used"] is False
    assert report["direct_acquisition_mode"] == LIVE_TAIL_MODE


def test_b4_backfill_uses_the_exact_before_signature(db_path) -> None:
    sig_a = _sig("SigA")
    connection = sqlite3.connect(db_path)
    try:
        dmd.ensure_direct_migration_cursor(connection, now=_NOW)
        dmd.advance_direct_migration_cursor(
            connection, signature=sig_a, slot=101, covered_count=1, now=_NOW
        )
        connection.commit()
    finally:
        connection.close()

    transport = RecordingTransport({sig_a: []}, {})
    report = _run(db_path, transport, mode=BACKFILL_MODE)
    assert transport.page_payloads[0]["cursor_before"] == sig_a
    assert report["cursor_before"] == sig_a
    assert report["cursor_used"] is True


def test_b5_page_limit_never_exceeds_transaction_coverage(db_path) -> None:
    rows = [_row(_sig(f"Cov{i}"), 200 + i) for i in range(6)]
    transactions = {row["signature"]: _non_migration_tx(row["slot"]) for row in rows}
    transport = RecordingTransport({None: rows}, transactions)
    _run(db_path, transport)

    assert transport.page_payloads[0]["signature_limit"] == _COOPERATIVE_LOOKUPS
    assert len(transport.transaction_signatures) <= _COOPERATIVE_LOOKUPS
    assert len(transport.transaction_signatures) == 6


# --------------------------------------------------------------------------- #
# B6 / B7 / B8 / B9 — the contiguous cursor advancement law                    #
# --------------------------------------------------------------------------- #


def test_b6_bootstrap_establishes_a_contiguous_cursor(db_path) -> None:
    rows = [_row(_sig(chr(65 + i) * 4), 300 + i) for i in range(6)]
    transactions = {row["signature"]: _non_migration_tx(row["slot"]) for row in rows}
    transport = RecordingTransport({None: rows}, transactions)

    before = _cursor(db_path)
    assert before is None or before.continuity_state == CONTINUITY_UNINITIALIZED

    _run(db_path, transport)
    cursor = _cursor(db_path)
    assert cursor.continuity_state == CONTINUITY_CONTIGUOUS
    assert cursor.next_before_signature == rows[-1]["signature"]
    assert cursor.next_before_slot == rows[-1]["slot"]
    assert cursor.pages_advanced == 1
    assert cursor.signatures_covered == 6
    assert cursor.pump_contract_hash == PUMP_IDL_SHA256
    assert cursor.decoder_version == DIRECT_PUMP_MIGRATION_DECODER_VERSION


def test_b7_partial_contiguous_advance_stops_at_the_source_failure(db_path) -> None:
    rows = [_row(_sig(f"Part{i}"), 400 + i) for i in range(6)]
    transactions = {
        rows[0]["signature"]: _non_migration_tx(400),
        rows[1]["signature"]: _non_migration_tx(401),
        rows[2]["signature"]: _source_failure_tx(),
    }
    transport = RecordingTransport({None: rows}, transactions)
    _run(db_path, transport)

    # D/E/F were never inspected.
    assert transport.transaction_signatures == [
        rows[0]["signature"],
        rows[1]["signature"],
        rows[2]["signature"],
    ]
    cursor = _cursor(db_path)
    assert cursor.next_before_signature == rows[1]["signature"]

    # The next BACKFILL must see C again.
    backfill_rows = rows[2:]
    backfill = RecordingTransport(
        {rows[1]["signature"]: backfill_rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in backfill_rows},
    )
    _run(db_path, backfill, mode=BACKFILL_MODE, key="slice-b-2")
    assert backfill.transaction_signatures[0] == rows[2]["signature"]


def test_b8_first_row_source_failure_never_advances(db_path) -> None:
    rows = [_row(_sig(f"Head{i}"), 500 + i) for i in range(6)]
    transport = RecordingTransport(
        {None: rows}, {rows[0]["signature"]: _source_failure_tx()}
    )
    _run(db_path, transport)

    assert transport.transaction_signatures == [rows[0]["signature"]]
    cursor = _cursor(db_path)
    assert cursor.next_before_signature is None
    assert cursor.next_before_slot is None
    assert cursor.continuity_state == CONTINUITY_UNINITIALIZED


def test_b9_definitive_non_migration_is_covered_not_a_provider_failure(
    db_path,
) -> None:
    rows = [_row(_sig("Def0"), 600)]
    transport = RecordingTransport({None: rows}, {rows[0]["signature"]: _non_migration_tx(600)})
    report = _run(db_path, transport)

    walk = report["page_walk"]
    assert [entry["outcome"] for entry in walk] == [dmd.COVERED_NON_MIGRATION]
    assert report["migration_intake"]["transaction_source_failures"] == []
    assert report["status"] == "COMPLETE"
    assert _cursor(db_path).next_before_signature == rows[0]["signature"]


# --------------------------------------------------------------------------- #
# B10 / B11 — canonical persistence for both variants                          #
# --------------------------------------------------------------------------- #


def _canonical_case(db_path, tx, infos, mint, signature):
    rows = [_row(signature, int(tx["slot"]))]
    transport = RecordingTransport({None: rows}, {signature: {"result": tx}})
    report = _run(
        db_path, transport, verifier_factory=_verifier_factory(tx, infos)
    )
    return transport, report


def test_b10_migrate_v2_persists_canonically_and_advances(db_path) -> None:
    tx, infos, mint, pool = _migrate_v2_case()
    signature = _sig("V2Sig")
    transport, report = _canonical_case(db_path, tx, infos, mint, signature)

    assert transport.page_count == 1
    assert report["confirmed_this_cycle"] == [mint]
    connection = connect_operational(db_path)
    try:
        rows = export_graduated_candidates(connection)
    finally:
        connection.close()
    assert [str(row["mint_identity"]) for row in rows] == [mint]
    assert str(rows[0]["pumpswap_pool"]) == pool
    assert _cursor(db_path).next_before_signature == signature
    assert report["canonically_persisted_signatures"] == [signature]


def test_b11_legacy_migrate_persists_canonically_and_advances(db_path) -> None:
    tx, infos, mint, pool = _legacy_migration_case()
    signature = _sig("LegacySig")
    _transport, report = _canonical_case(db_path, tx, infos, mint, signature)

    assert report["confirmed_this_cycle"] == [mint]
    connection = connect_operational(db_path)
    try:
        rows = export_graduated_candidates(connection)
    finally:
        connection.close()
    assert [str(row["mint_identity"]) for row in rows] == [mint]
    assert str(rows[0]["pumpswap_pool"]) == pool
    assert _cursor(db_path).next_before_signature == signature


# --------------------------------------------------------------------------- #
# B12 / B13 / B14 — verification failure, contract blocker, contract reset     #
# --------------------------------------------------------------------------- #


def test_b12_pumpswap_failure_blocks_cursor_advance(db_path) -> None:
    tx, _infos, _mint, _pool = _migrate_v2_case()
    signature = _sig("BlockedVerify")
    rows = [_row(signature, int(tx["slot"]))]
    transport = RecordingTransport({None: rows}, {signature: {"result": tx}})
    report = _run(db_path, transport, verifier_factory=_failing_verifier)

    connection = connect_operational(db_path)
    try:
        assert export_graduated_candidates(connection) == []
    finally:
        connection.close()
    assert report["confirmed_this_cycle"] == []
    cursor = _cursor(db_path)
    assert cursor.next_before_signature is None
    assert cursor.continuity_state == CONTINUITY_UNINITIALIZED
    # F: a provider failure inside verification is a source failure, never a
    # candidate-local permanent rejection.
    assert report["verifications"][0]["verified"] is False


def test_b13_unsupported_migration_contract_blocks_the_cursor(db_path) -> None:
    rows = [_row(_sig("BlockA"), 700), _row(_sig("BlockB"), 701)]
    transport = RecordingTransport(
        {None: rows},
        {
            rows[0]["signature"]: _non_migration_tx(700),
            rows[1]["signature"]: _unsupported_contract_tx(),
        },
    )
    _run(db_path, transport)

    cursor = _cursor(db_path)
    assert cursor.continuity_state == CONTINUITY_BLOCKED_CONTRACT
    assert cursor.last_block_reason
    assert len(cursor.last_block_reason) <= 120
    # The blocked signature was never crossed.
    assert cursor.next_before_signature == rows[0]["signature"]

    # Automatic BACKFILL under the same contract identity issues zero requests.
    blocked = RecordingTransport({}, {})
    report = _run(db_path, blocked, mode=BACKFILL_MODE, key="slice-b-blocked")
    assert blocked.page_count == 0
    assert blocked.transaction_signatures == []
    assert report["signature_pages_requested"] == 0
    assert report["cursor_skip_reason"] == (
        f"BACKFILL_NOT_PERMITTED_{CONTINUITY_BLOCKED_CONTRACT}"
    )


def test_b14_new_contract_identity_starts_a_separate_cursor(db_path, monkeypatch) -> None:
    connection = sqlite3.connect(db_path)
    try:
        dmd.ensure_direct_migration_cursor(connection, now=_NOW)
        dmd.mark_direct_migration_cursor_contract_blocked(
            connection,
            reason="migrate_v2_account_layout_mismatch",
            now=_NOW,
            signature=_sig("OldPos"),
            slot=900,
        )
        connection.commit()
    finally:
        connection.close()

    monkeypatch.setattr(
        dmd, "DIRECT_PUMP_MIGRATION_DECODER_VERSION", "DECODER_V_NEXT"
    )
    fresh = _cursor(db_path)
    assert fresh is None
    connection = sqlite3.connect(db_path)
    try:
        created = dmd.ensure_direct_migration_cursor(connection, now=_NOW)
        connection.commit()
        rows = connection.execute(
            "SELECT decoder_version, continuity_state, next_before_signature "
            "FROM printer_direct_pump_migration_cursor ORDER BY decoder_version"
        ).fetchall()
    finally:
        connection.close()

    assert created.continuity_state == CONTINUITY_UNINITIALIZED
    assert created.next_before_signature is None
    assert len(rows) == 2
    old = [row for row in rows if row[0] == DIRECT_PUMP_MIGRATION_DECODER_VERSION][0]
    # The old contract's cursor is untouched, never mutated into the new identity.
    assert old[1] == CONTINUITY_BLOCKED_CONTRACT
    assert old[2] == _sig("OldPos")


# --------------------------------------------------------------------------- #
# B15 / B16 / B17 — live tail vs history, restart safety, exhaustion           #
# --------------------------------------------------------------------------- #


def test_b15_live_tail_never_resets_an_established_cursor(db_path) -> None:
    old = _sig("OldSig")
    connection = sqlite3.connect(db_path)
    try:
        dmd.ensure_direct_migration_cursor(connection, now=_NOW)
        dmd.advance_direct_migration_cursor(
            connection, signature=old, slot=1_000, covered_count=6, now=_NOW
        )
        connection.commit()
    finally:
        connection.close()

    rows = [_row(_sig(f"New{i}"), 2_000 + i) for i in range(6)]
    transport = RecordingTransport(
        {None: rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in rows},
    )
    _run(db_path, transport)

    cursor = _cursor(db_path)
    assert cursor.next_before_signature == old
    assert cursor.next_before_slot == 1_000
    assert cursor.continuity_state == CONTINUITY_CONTIGUOUS
    assert cursor.last_live_tail_at == _NOW


def test_b16_backfill_advances_across_process_restart(db_path) -> None:
    rows = [_row(_sig(f"Run1{i}"), 3_000 + i) for i in range(6)]
    first = RecordingTransport(
        {None: rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in rows},
    )
    _run(db_path, first)
    assert _cursor(db_path).next_before_signature == rows[-1]["signature"]

    # New connection + newly constructed transport: no in-memory continuity.
    second_rows = [_row(_sig(f"Run2{i}"), 4_000 + i) for i in range(2)]
    second = RecordingTransport(
        {rows[-1]["signature"]: second_rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in second_rows},
    )
    _run(db_path, second, mode=BACKFILL_MODE, key="slice-b-restart")
    assert second.page_payloads[0]["cursor_before"] == rows[-1]["signature"]
    assert _cursor(db_path).next_before_signature == second_rows[-1]["signature"]


def test_b17_empty_backfill_page_exhausts_backward_traversal(db_path) -> None:
    anchor = _sig("Anchor")
    connection = sqlite3.connect(db_path)
    try:
        dmd.ensure_direct_migration_cursor(connection, now=_NOW)
        dmd.advance_direct_migration_cursor(
            connection, signature=anchor, slot=5_000, covered_count=1, now=_NOW
        )
        connection.commit()
    finally:
        connection.close()

    empty = RecordingTransport({anchor: []}, {})
    _run(db_path, empty, mode=BACKFILL_MODE)
    assert _cursor(db_path).continuity_state == CONTINUITY_EXHAUSTED

    # Live tail still runs; automatic backfill issues zero source calls.
    live_rows = [_row(_sig("Live0"), 6_000)]
    live = RecordingTransport(
        {None: live_rows}, {live_rows[0]["signature"]: _non_migration_tx(6_000)}
    )
    _run(db_path, live, key="slice-b-live")
    assert live.page_count == 1

    blocked = RecordingTransport({}, {})
    report = _run(db_path, blocked, mode=BACKFILL_MODE, key="slice-b-exhausted")
    assert blocked.page_count == 0
    assert report["cursor_skip_reason"] == (
        f"BACKFILL_NOT_PERMITTED_{CONTINUITY_EXHAUSTED}"
    )
    assert _cursor(db_path).continuity_state == CONTINUITY_EXHAUSTED


# --------------------------------------------------------------------------- #
# B18 — no fallback of any kind                                                #
# --------------------------------------------------------------------------- #


def test_b18_targeted_page_failure_has_no_fallback(db_path) -> None:
    class FailingPageTransport(RecordingTransport):
        def __call__(self, context):
            if context.request.request_kind == SIGNATURE_PAGE_REQUEST_KIND:
                self.page_payloads.append(dict(context.request.payload or {}))
                return {
                    "fixture_status": "failure",
                    "failure_type": "direct_pump_rpc_rate_limited",
                    "failure_message": "Solana RPC HTTP 429",
                }
            raise AssertionError("no second source operation is permitted")

    transport = FailingPageTransport({}, {})
    report = _run(db_path, transport)

    assert transport.page_count == 1
    assert transport.page_payloads[0]["indexed_address"] == PUMP_WITHDRAW_AUTHORITY_ID
    assert transport.transaction_signatures == []
    assert report["status"] == "PROVIDER_FAILURE"
    assert _cursor(db_path).continuity_state == CONTINUITY_UNINITIALIZED

    for module in (
        ROOT / "src/printer_v1/sources/direct_pump_migration.py",
        ROOT / "src/printer_v1/discovery/direct_migration_discovery.py",
    ):
        source = module.read_text(encoding="utf-8")
        assert "pumpportal" not in source.lower()
        assert "birdeye" not in source.lower()
        assert '"until"' not in source

    # The transport refuses any other indexed address before an RPC is built.
    from printer_v1.sources.direct_pump_migration import (
        build_direct_pump_migration_transport,
    )

    live = build_direct_pump_migration_transport(rpc_url="https://rpc.invalid/x")

    class _Request:
        request_kind = SIGNATURE_PAGE_REQUEST_KIND
        payload = {
            "indexed_address": PUMP_PROGRAM_ID,
            "cursor_before": None,
            "signature_limit": 6,
        }

    class _Context:
        request = _Request()

    refused = live(_Context())
    assert refused["failure_type"] == "direct_pump_indexed_address_not_allowed"


# --------------------------------------------------------------------------- #
# B23 / B24 — one-quantum fanout and the unchanged G bound                     #
# --------------------------------------------------------------------------- #


def test_b23_one_quantum_source_fanout_is_bounded(db_path) -> None:
    tx, infos, mint, _pool = _migrate_v2_case()
    signature = _sig("Fanout")
    rows = [_row(signature, int(tx["slot"]))] + [
        _row(_sig(f"Fan{i}"), 7_000 + i) for i in range(5)
    ]
    transport = RecordingTransport({None: rows}, {signature: {"result": tx}})
    report = _run(
        db_path, transport, verifier_factory=_verifier_factory(tx, infos)
    )

    assert transport.page_count <= 1
    assert len(transport.transaction_signatures) <= _COOPERATIVE_LOOKUPS
    coverage = report["source_request_coverage"]
    pages = [
        row
        for row in coverage
        if row["request_kind"] == SIGNATURE_PAGE_REQUEST_KIND
    ]
    lookups = [
        row for row in coverage if row["request_kind"] == TRANSACTION_REQUEST_KIND
    ]
    verifiers = [
        row
        for row in coverage
        if row["request_kind"] == "pumpswap_signature_pool_resolution"
    ]
    assert len(pages) <= 1
    assert len(lookups) <= 6
    assert len(verifiers) <= 1
    assert len(coverage) == len(pages) + len(lookups) + len(verifiers)


def test_b24_direct_migration_quantum_bound_is_unchanged() -> None:
    bound = acquisition_quantum_bound(AcquisitionQuantumKind.DIRECT_MIGRATION)
    assert bound.worst_case_seconds == 115.0
    assert bound.transport_count == 11


# --------------------------------------------------------------------------- #
# B27 / B28 / B29 — ownership boundaries                                       #
# --------------------------------------------------------------------------- #


def test_b27_candidate_cursor_ranges_stay_untouched(db_path) -> None:
    def _count(table: str) -> int:
        connection = sqlite3.connect(db_path)
        try:
            return int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
        finally:
            connection.close()

    before = _count("printer_candidate_cursor_ranges")

    rows = [_row(_sig(f"Own{i}"), 8_000 + i) for i in range(3)]
    live = RecordingTransport(
        {None: rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in rows},
    )
    _run(db_path, live)

    backfill_rows = [_row(_sig("Own9"), 8_100)]
    backfill = RecordingTransport(
        {rows[-1]["signature"]: backfill_rows},
        {backfill_rows[0]["signature"]: _non_migration_tx(8_100)},
    )
    _run(db_path, backfill, mode=BACKFILL_MODE, key="slice-b-own")

    assert _count("printer_candidate_cursor_ranges") - before == 0
    assert _count("printer_direct_pump_migration_cursor") == 1


def test_b28_duplicate_canonical_migration_stays_one_identity(db_path) -> None:
    tx, infos, mint, _pool = _migrate_v2_case()
    signature = _sig("Replay")
    for index in range(2):
        rows = [_row(signature, int(tx["slot"]))]
        transport = RecordingTransport({None: rows}, {signature: {"result": tx}})
        report = _run(
            db_path,
            transport,
            verifier_factory=_verifier_factory(tx, infos),
            key=f"slice-b-replay-{index}",
        )
        assert report["status"] == "COMPLETE"
        assert report["canonically_persisted_signatures"] == [signature]

    connection = connect_operational(db_path)
    try:
        rows = export_graduated_candidates(connection)
    finally:
        connection.close()
    assert len(rows) == 1
    assert str(rows[0]["mint_identity"]) == mint
    assert _cursor(db_path).next_before_signature == signature


def test_b29_no_forbidden_capability_rows(db_path) -> None:
    forbidden = (
        "printer_paper_decisions",
        "printer_paper_positions",
        "printer_paper_trades",
        "printer_paper_trade_audit",
        "printer_episode_memory",
        "printer_memory_retrieval",
        "printer_memory_factory_runs",
    )

    def _counts() -> dict:
        connection = sqlite3.connect(db_path)
        try:
            values = {}
            for table in forbidden:
                exists = connection.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,),
                ).fetchone()
                values[table] = (
                    0
                    if exists is None
                    else int(
                        connection.execute(
                            f"SELECT COUNT(*) FROM {table}"
                        ).fetchone()[0]
                    )
                )
            return values
        finally:
            connection.close()

    before = _counts()
    tx, infos, _mint, _pool = _migrate_v2_case()
    signature = _sig("Forbidden")
    rows = [_row(signature, int(tx["slot"]))]
    transport = RecordingTransport({None: rows}, {signature: {"result": tx}})
    report = _run(db_path, transport, verifier_factory=_verifier_factory(tx, infos))

    assert _counts() == before
    assert report["forbidden_delta_total"] == 0


# --------------------------------------------------------------------------- #
# Migration 058                                                                #
# --------------------------------------------------------------------------- #


def test_migration_058_is_the_canonical_head_and_edits_nothing_prior() -> None:
    names = canonical_migration_names()
    assert names[-1] == "058_direct_pump_migration_cursor.sql"
    assert len(names) == 58
    sql = (MIGRATIONS_DIR / names[-1]).read_text(encoding="utf-8")
    assert "CREATE TABLE printer_direct_pump_migration_cursor" in sql
    assert "ALTER TABLE" not in sql
    assert "DROP " not in sql
    statements = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    )
    assert "printer_candidate_cursor_ranges" not in statements


def test_migration_058_applies_after_057_and_to_an_empty_database(tmp_path) -> None:
    names = list(canonical_migration_names())
    staged = tmp_path / "staged.sqlite3"
    connection = sqlite3.connect(staged)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS printer_schema_migrations ("
            "version TEXT PRIMARY KEY, applied_at TEXT NOT NULL "
            "DEFAULT (datetime('now')))"
        )
        for name in names[:-1]:
            connection.executescript(
                (MIGRATIONS_DIR / name).read_text(encoding="utf-8")
            )
            connection.execute(
                "INSERT INTO printer_schema_migrations (version) VALUES (?)", (name,)
            )
        connection.commit()
        assert (
            connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='printer_direct_pump_migration_cursor'"
            ).fetchone()
            is None
        )
    finally:
        connection.close()

    apply_migrations(staged)
    fresh = tmp_path / "fresh.sqlite3"
    apply_migrations(fresh)

    for path in (staged, fresh):
        connection = sqlite3.connect(path)
        try:
            applied = [
                str(row[0])
                for row in connection.execute(
                    "SELECT version FROM printer_schema_migrations ORDER BY version"
                )
            ]
            assert applied == names
            columns = {
                row[1]
                for row in connection.execute(
                    "PRAGMA table_info(printer_direct_pump_migration_cursor)"
                )
            }
            assert {
                "network",
                "indexed_address",
                "pump_contract_hash",
                "decoder_version",
                "next_before_signature",
                "next_before_slot",
                "continuity_state",
                "pages_advanced",
                "signatures_covered",
                "last_live_tail_at",
                "last_backfill_at",
                "last_block_reason",
                "created_at",
                "updated_at",
            } == columns
            assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            connection.close()


def test_migration_058_rejects_incoherent_cursor_rows(db_path) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        base = (
            "INSERT INTO printer_direct_pump_migration_cursor("
            "network,indexed_address,pump_contract_hash,decoder_version,"
            "next_before_signature,next_before_slot,continuity_state,"
            "last_block_reason,created_at,updated_at) VALUES "
        )
        # CONTIGUOUS without a position.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                base
                + "('solana-mainnet','a','b','c',NULL,NULL,'CONTIGUOUS',NULL,?,?)",
                (_NOW, _NOW),
            )
        # Half a position.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                base
                + "('solana-mainnet','a','b','c','sig',NULL,'EXHAUSTED',NULL,?,?)",
                (_NOW, _NOW),
            )
        # BLOCKED_CONTRACT without a reason.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                base
                + "('solana-mainnet','a','b','c',NULL,NULL,'BLOCKED_CONTRACT',NULL,?,?)",
                (_NOW, _NOW),
            )
        # Wrong network.
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                base
                + "('solana-devnet','a','b','c',NULL,NULL,'UNINITIALIZED',NULL,?,?)",
                (_NOW, _NOW),
            )
    finally:
        connection.close()


# --------------------------------------------------------------------------- #
# Cooperative production path: B19 / B20 / B21 / B22 / B25 / B26 / B30         #
# --------------------------------------------------------------------------- #


def _cooperative_supply(
    db_path,
    transport,
    *,
    stage_budget,
    direct_mode=LIVE_TAIL_MODE,
    verifier_factory=None,
    seed="slice-b-coop",
    cycle_id="cycle-b-2",
):
    from printer_v1.discovery.permanent_discovery_availability import (
        build_campaign_source_request_scope,
    )
    from printer_v1.operator_cli.graduated_supply_front_door import (
        build_graduated_supply,
    )

    scope = build_campaign_source_request_scope(
        execution_id=f"exec-{cycle_id}",
        campaign_id="campaign-b",
        run_id="campaign-run-b",
        cycle_id=cycle_id,
    )
    return build_graduated_supply(
        db_path,
        cycle_seed=seed,
        migration_transport=transport,
        verifier_transport_factory=verifier_factory or _never_verify,
        now=_NOW,
        permanent_availability=True,
        campaign_source_request_scope=scope,
        discovery_request_key_prefix=scope.request_key_root,
        front_door_request_key_prefix=scope.request_key_root,
        campaign_id=scope.campaign_id,
        execution_id=scope.execution_id,
        run_id=scope.run_id,
        cycle_id=scope.cycle_id,
        cooperative_resume=True,
        cooperative_quantum=True,
        cooperative_phase="DIRECT_MIGRATION",
        cooperative_stage_budget=stage_budget,
        cooperative_direct_mode=direct_mode,
        max_candidates=1,
    )


def _fresh_budget():
    from printer_v1.discovery.permanent_discovery_availability import StageBudget

    return StageBudget.permanent_discovery_default()


def test_b19_clean_live_tail_yields_then_schedules_backfill(db_path) -> None:
    rows = [_row(_sig(f"Coop{i}"), 9_000 + i) for i in range(6)]
    transport = RecordingTransport(
        {None: rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in rows},
    )
    budget = _fresh_budget()
    supply = _cooperative_supply(db_path, transport, stage_budget=budget)

    diagnostics = supply.diagnostics
    assert transport.page_count == 1
    assert diagnostics["cooperative_phase"] == "DIRECT_MIGRATION"
    assert diagnostics["next_cooperative_phase"] == "DIRECT_MIGRATION"
    assert diagnostics["next_direct_acquisition_mode"] == BACKFILL_MODE
    assert diagnostics["direct_acquisition_mode"] == LIVE_TAIL_MODE
    assert diagnostics["direct_live_tail_completed"] is True
    assert diagnostics["direct_backfill_completed"] is False
    assert diagnostics["direct_migration_cursor"]["continuity_state"] == (
        CONTINUITY_CONTIGUOUS
    )
    assert supply.terminal == "ACQUISITION_QUANTUM_YIELDED"
    # No BACKFILL source call inside the same claim.
    assert [payload["cursor_before"] for payload in transport.page_payloads] == [None]


def test_b20_backfill_claim_runs_one_page_then_hands_off_to_market(db_path) -> None:
    budget = _fresh_budget()
    live_rows = [_row(_sig(f"Hand{i}"), 10_000 + i) for i in range(6)]
    live = RecordingTransport(
        {None: live_rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in live_rows},
    )
    first = _cooperative_supply(db_path, live, stage_budget=budget)
    assert first.diagnostics["next_direct_acquisition_mode"] == BACKFILL_MODE

    backfill_rows = [_row(_sig(f"Older{i}"), 11_000 + i) for i in range(3)]
    backfill = RecordingTransport(
        {live_rows[-1]["signature"]: backfill_rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in backfill_rows},
    )
    second = _cooperative_supply(
        db_path,
        backfill,
        stage_budget=budget,
        direct_mode=BACKFILL_MODE,
        cycle_id="cycle-b-3",
    )

    assert backfill.page_count == 1
    assert backfill.page_payloads[0]["cursor_before"] == live_rows[-1]["signature"]
    diagnostics = second.diagnostics
    assert diagnostics["direct_backfill_completed"] is True
    assert diagnostics["next_cooperative_phase"] == "MARKET_DISCOVERY"
    assert diagnostics["next_direct_acquisition_mode"] == LIVE_TAIL_MODE
    assert second.terminal == "ACQUISITION_QUANTUM_YIELDED"
    assert _cursor(db_path).next_before_signature == backfill_rows[-1]["signature"]


def test_b21_live_tail_candidate_skips_this_attempt_backfill(db_path) -> None:
    tx, infos, _mint, _pool = _migrate_v2_case()
    signature = _sig("CoopHit")
    rows = [_row(signature, int(tx["slot"]))]
    transport = RecordingTransport({None: rows}, {signature: {"result": tx}})
    supply = _cooperative_supply(
        db_path,
        transport,
        stage_budget=_fresh_budget(),
        verifier_factory=_verifier_factory(tx, infos),
    )

    diagnostics = supply.diagnostics
    assert diagnostics["confirmed_this_cycle"] == 1
    assert diagnostics["next_cooperative_phase"] == "MARKET_DISCOVERY"
    assert diagnostics["next_direct_acquisition_mode"] == LIVE_TAIL_MODE
    assert transport.page_count == 1


def test_b22_live_tail_source_failure_never_schedules_backfill(db_path) -> None:
    class FailingPage(RecordingTransport):
        def __call__(self, context):
            if context.request.request_kind == SIGNATURE_PAGE_REQUEST_KIND:
                self.page_payloads.append(dict(context.request.payload or {}))
                return {
                    "fixture_status": "failure",
                    "failure_type": "direct_pump_rpc_rate_limited",
                    "failure_message": "Solana RPC HTTP 429",
                }
            raise AssertionError("no second same-source page is permitted")

    transport = FailingPage({}, {})
    supply = _cooperative_supply(db_path, transport, stage_budget=_fresh_budget())

    diagnostics = supply.diagnostics
    assert transport.page_count == 1
    assert diagnostics["next_direct_acquisition_mode"] != BACKFILL_MODE
    assert diagnostics["next_cooperative_phase"] == "MARKET_DISCOVERY"


def test_b25_lifecycle_deadline_blocks_both_direct_modes() -> None:
    from printer_v1.operator_cli.authoritative_live_operational_campaign import (
        _next_later_cycle_quantum_kind,
    )
    from printer_v1.operator_cli.one_command_15m_factory import (
        _later_cycle_acquisition_deadline_conflict,
    )

    bound = acquisition_quantum_bound(AcquisitionQuantumKind.DIRECT_MIGRATION)
    now = datetime(2026, 8, 17, 12, 0, tzinfo=timezone.utc)

    for mode in (LIVE_TAIL_MODE, BACKFILL_MODE):
        progress = {
            "cycle": {
                "cooperative_phase": "DIRECT_MIGRATION",
                "direct_acquisition_mode": mode,
            }
        }
        # Both modes are the same DIRECT_MIGRATION unit under the same bound.
        assert _next_later_cycle_quantum_kind(progress) is (
            AcquisitionQuantumKind.DIRECT_MIGRATION
        )
        assert (
            _later_cycle_acquisition_deadline_conflict(
                now=now,
                earliest_lifecycle_deadline=now + timedelta(seconds=30),
                worst_case_quantum_seconds=bound.worst_case_seconds,
            )
            is True
        )
        assert (
            _later_cycle_acquisition_deadline_conflict(
                now=now,
                earliest_lifecycle_deadline=now + timedelta(seconds=116),
                worst_case_quantum_seconds=bound.worst_case_seconds,
            )
            is False
        )


def test_b26_stage_budget_is_cumulative_across_live_tail_and_backfill(
    db_path,
) -> None:
    budget = _fresh_budget()
    tx, infos, _mint, _pool = _migrate_v2_case()
    signature = _sig("BudgetHit")

    live_rows = [_row(_sig(f"Bud{i}"), 12_000 + i) for i in range(6)]
    live = RecordingTransport(
        {None: live_rows},
        {row["signature"]: _non_migration_tx(row["slot"]) for row in live_rows},
    )
    _cooperative_supply(db_path, live, stage_budget=budget)
    after_live = budget.snapshot()
    assert after_live["used_by_stage"]["intake"] == 1
    assert after_live["used_by_stage"]["protocol_confirmation"] == 0

    backfill_rows = [_row(signature, int(tx["slot"]))]
    backfill = RecordingTransport(
        {live_rows[-1]["signature"]: backfill_rows}, {signature: {"result": tx}}
    )
    _cooperative_supply(
        db_path,
        backfill,
        stage_budget=budget,
        direct_mode=BACKFILL_MODE,
        verifier_factory=_verifier_factory(tx, infos),
        cycle_id="cycle-b-4",
    )
    after_backfill = budget.snapshot()

    # Same object; availability never increases; charges are cumulative.
    assert after_backfill["used_by_stage"]["intake"] == 2
    assert after_backfill["used_by_stage"]["protocol_confirmation"] == 1
    assert (
        after_backfill["total_remaining"] <= after_live["total_remaining"]
    )
    assert budget.total_ceiling == _fresh_budget().total_ceiling


def test_b30_slice_b_adds_no_new_budget_capacity() -> None:
    from printer_v1.discovery.permanent_discovery_availability import (
        STAGE_RESERVATIONS,
    )
    from printer_v1.discovery.eligible_token_supply import (
        DEFAULT_DISCOVERY_OPERATION_BUDGET,
        LIFECYCLE_OPERATION_CEILING,
    )

    assert dict(STAGE_RESERVATIONS) == {
        "intake": 3,
        "market_batching": 2,
        "reconciliation": 6,
        "protocol_confirmation": 7,
        "holder_safety": 8,
        "final_refresh_handoff": 4,
    }
    assert DEFAULT_DISCOVERY_OPERATION_BUDGET == 30
    assert LIFECYCLE_OPERATION_CEILING == 45
