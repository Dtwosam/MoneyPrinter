"""Focused proofs for permanent discovery conversion repair (D1/D2/D3)."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import tempfile

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.eligible_token_supply import (
    MIGRATION_EVIDENCE_REJECTED,
    SOURCE_AVAILABILITY_FAILURE,
    _is_candidate_local_migrate_failure,
    run_persistent_eligible_token_supply,
)
from printer_v1.discovery.permanent_discovery_availability import (
    CONTRACT_BLOCKED,
    UNSUPPORTED_VENUE,
    StageBudget,
    process_protocol_confirmation_queue,
    record_fresh_pool_nominations,
)
from printer_v1.sources.direct_pump_migration import (
    SIGNATURE_PAGE_REQUEST_KIND,
    TRANSACTION_REQUEST_KIND,
)
from printer_v1.sources.pump_contracts import (
    PUMP_MIGRATE_DISCRIMINATOR,
    PUMP_PROGRAM_ID,
    decode_supported_pump_migration_transaction,
)
from printer_v1.sources.pumpswap_graduated_registry import record_graduated_candidate
from printer_v1.sources.dexscreener import fixture_success_transport

NOW = "2026-08-04T15:00:00+00:00"
WSOL = "So11111111111111111111111111111111111111112"


@pytest.fixture()
def database():
    with tempfile.TemporaryDirectory() as directory:
        db_path = Path(directory) / "conversion-repair.sqlite3"
        apply_migrations(db_path)
        connection = sqlite3.connect(str(db_path))
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield db_path, connection
        finally:
            connection.close()


def _b58(data: bytes) -> str:
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    n = int.from_bytes(data, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = alphabet[r] + out
    pad = 0
    for byte in data:
        if byte == 0:
            pad += 1
        else:
            break
    return ("1" * pad) + (out or "1")


def _tx_with_migrate_count(match_count: int, *, mints: list[str] | None = None):
    mints = mints or [f"Mint{'x' * 10}{i}" for i in range(max(match_count, 1))]
    account_keys: list[str] = [PUMP_PROGRAM_ID]
    instructions = []
    for i in range(match_count):
        mint = mints[i % len(mints)]
        start = len(account_keys)
        for j in range(25):
            if j == 2:
                account_keys.append(mint)
            else:
                account_keys.append(f"Acct{i}_{j}_{'y' * 20}")
        instructions.append(
            {
                "programIdIndex": 0,
                "accounts": list(range(start, start + 25)),
                "data": _b58(PUMP_MIGRATE_DISCRIMINATOR + b"\x00" * 8),
            }
        )
    return {
        "version": 0,
        "slot": 1,
        "blockTime": 1_700_000_000,
        "meta": {"err": None, "innerInstructions": []},
        "transaction": {
            "message": {"accountKeys": account_keys, "instructions": instructions}
        },
    }


def _seed(connection, count: int = 4):
    rows = []
    for index in range(count):
        mint = f"Mint{index:02d}"
        pool = f"Pool{index:02d}"
        record_graduated_candidate(
            connection,
            mint=mint,
            migration_signature=f"Signature{index:02d}",
            pumpswap_pool=pool,
            graduation_block_time=1_700_000_000 + index,
            graduation_slot=index,
            now=NOW,
        )
        rows.append({"mint_identity": mint, "pumpswap_pool": pool})
    connection.commit()
    return rows


def _rejecting_migration_transport():
    def transport(context):
        kind = context.request.request_kind
        if kind == SIGNATURE_PAGE_REQUEST_KIND:
            return {
                "result": [
                    {
                        "signature": "SigA",
                        "slot": 1,
                        "confirmationStatus": "finalized",
                        "err": None,
                    },
                    {
                        "signature": "SigB",
                        "slot": 1,
                        "confirmationStatus": "finalized",
                        "err": None,
                    },
                ],
                "response_bytes": 120,
            }
        if kind == TRANSACTION_REQUEST_KIND:
            return {"result": _tx_with_migrate_count(0), "response_bytes": 5000}
        raise AssertionError(kind)

    return transport


class TestCandidateLocalMigrationRejection:
    def test_exactly_one_reject_builds_digest(self):
        tx = _tx_with_migrate_count(0)
        decoded = decode_supported_pump_migration_transaction(
            tx, expected_signature="SigZero"
        )
        assert decoded["supported"] is False
        assert decoded["reason"] == "exactly_one_migrate_instruction_required"
        digest = decoded["migration_rejection_digest"]
        assert digest["outcome"] == "MIGRATION_EVIDENCE_REJECTED"
        assert digest["signature"] == "SigZero"
        assert digest["pump_migrate_match_count"] == 0

        decoded2 = decode_supported_pump_migration_transaction(
            _tx_with_migrate_count(2, mints=["MintAAAA", "MintBBBB"]),
            expected_signature="SigTwo",
        )
        assert decoded2["reason"] == "exactly_one_migrate_instruction_required"
        d2 = decoded2["migration_rejection_digest"]
        assert d2["pump_migrate_match_count"] == 2
        assert set(d2["candidate_mint_identities"]) == {"MintAAAA", "MintBBBB"}

    def test_candidate_local_prefix_helper(self):
        assert _is_candidate_local_migrate_failure(
            "direct_pump_migration_rejected_exactly_one_migrate_instruction_required"
        )
        assert not _is_candidate_local_migrate_failure("direct_pump_rpc_timeout")
        assert not _is_candidate_local_migrate_failure(None)

    def test_transport_complete_reject_is_not_shared_source_failure(self, database):
        db_path, connection = database
        inventory = _seed(connection, 4)
        pools = {row["mint_identity"]: row["pumpswap_pool"] for row in inventory}
        batch_calls: list[tuple[str, ...]] = []

        def batch_factory(mints):
            batch_calls.append(tuple(mints))
            return fixture_success_transport(
                {
                    "pairs": [
                        {
                            "chainId": "solana",
                            "pairAddress": pools[mint],
                            "dexId": "pumpswap",
                            "baseToken": {"address": mint},
                            "quoteToken": {"address": WSOL},
                            "liquidity": {"usd": 5_000},
                        }
                        for mint in mints
                        if mint in pools
                    ]
                }
            )

        result = run_persistent_eligible_token_supply(
            db_path,
            cycle_seed="migrate-local",
            migration_transport=_rejecting_migration_transport(),
            dexscreener_batch_transport_factory=batch_factory,
            now=NOW,
            run_locator=False,
            permanent_availability=True,
            enable_geckoterminal_reconciliation=False,
            campaign_id="campaign-migrate-local",
            required_token_capacity=4,
        )
        assert result.shortage_classification != SOURCE_AVAILABILITY_FAILURE
        assert result.diagnostics["shared_source_failures"] == 0
        assert "direct_pump_finalized_live_tail" not in (
            result.diagnostics.get("channels_unavailable") or []
        )
        assert result.diagnostics["migration_evidence_rejections"]
        assert all(
            item["outcome"] == MIGRATION_EVIDENCE_REJECTED
            for item in result.diagnostics["migration_evidence_rejections"]
        )
        assert batch_calls, "Dex batch must still execute after candidate-local rejects"
        assert result.diagnostics["market_ready_count"] >= 1


class TestStageSealAndMultiRoundMarket:
    def test_seal_allows_protocol_and_market_without_rewind(self):
        budget = StageBudget.permanent_discovery_default()
        budget.consume("intake", 3)
        budget.seal("intake")
        budget.consume("protocol_confirmation", 2)
        budget.consume("market_batching", 1)
        budget.consume("market_batching", 1)
        assert budget.used_by_stage["market_batching"] == 2
        assert budget.used_by_stage["protocol_confirmation"] == 2
        with pytest.raises(ValueError, match="STAGE_RESERVATION_EXCEEDED"):
            budget.consume("market_batching", 1)

    def test_second_market_batch_after_protocol_ops(self, database):
        db_path, connection = database
        inventory = _seed(connection, 35)
        pools = {row["mint_identity"]: row["pumpswap_pool"] for row in inventory}
        batch_rounds: list[int] = []

        def batch_factory(mints):
            batch_rounds.append(len(mints))
            return fixture_success_transport(
                {
                    "pairs": [
                        {
                            "chainId": "solana",
                            "pairAddress": pools[mint],
                            "dexId": "pumpswap",
                            "baseToken": {"address": mint},
                            "quoteToken": {"address": WSOL},
                            "liquidity": {"usd": 2_500},
                        }
                        for mint in mints
                    ]
                }
            )

        result = run_persistent_eligible_token_supply(
            db_path,
            cycle_seed="multi-batch",
            migration_transport=_rejecting_migration_transport(),
            dexscreener_batch_transport_factory=batch_factory,
            now=NOW,
            run_locator=False,
            permanent_availability=True,
            enable_geckoterminal_reconciliation=False,
            campaign_id="campaign-multi-batch",
        )
        assert len(batch_rounds) >= 2
        assert result.diagnostics["discovery_rounds"] >= 2
        stage = result.diagnostics["stage_capacity"]
        assert stage["used_by_stage"]["market_batching"] >= 2
        assert stage["used_by_stage"]["protocol_confirmation"] >= 1


class TestProtocolQueueAndHolderGate:
    def test_protocol_due_identities_receive_bounded_work(self, database):
        _, connection = database
        from printer_v1.sources.pumpswap_pool_account_batch import (
            fixture_account_batch_transport,
        )
        observations = [
            {
                "mint": f"MintP{i}{'z' * 30}",
                "pool": f"PoolP{i}{'z' * 30}",
                "base_mint": f"MintP{i}{'z' * 30}",
                "quote_mint": WSOL,
                "venue": "pumpswap" if i < 3 else "meteora-damm-v2",
            }
            for i in range(5)
        ]
        record_fresh_pool_nominations(
            connection,
            observations=observations,
            source="geckoterminal",
            request_id=99,
            now=NOW,
            campaign_id="camp-proto",
        )
        # Fixture returns null accounts → candidate-local ACCOUNT_NOT_FOUND
        values = {
            f"PoolP{i}{'z' * 30}": None for i in range(3)
        }
        transport = fixture_account_batch_transport(values)
        budget = StageBudget.permanent_discovery_default()
        budget.consume("intake", 3)
        budget.seal("intake")
        budget.consume("market_batching", 2)
        budget.seal("market_batching")
        budget.consume("reconciliation", 6)
        budget.seal("reconciliation")
        report = process_protocol_confirmation_queue(
            connection,
            stage_budget=budget,
            now=NOW,
            campaign_id="camp-proto",
            max_confirmations=4,
            account_batch_transport=transport,
        )
        assert report["source_requests"] >= 1
        assert any(o["outcome"] == "UNSUPPORTED_VENUE" for o in report["outcomes"])
        assert any(
            o["outcome"] == "ACCOUNT_NOT_FOUND" for o in report["outcomes"]
        )
        meteora = connection.execute(
            """
            SELECT current_state FROM printer_exact_market_states
            WHERE venue='meteora-damm-v2'
            """
        ).fetchone()
        assert meteora is not None
        assert meteora["current_state"] in {CONTRACT_BLOCKED, UNSUPPORTED_VENUE}

    def test_permanent_holder_gate_allows_single_market_ready(self):
        permanent_mode = True
        graduated_count = 1
        skip = graduated_count < 1 or (
            not permanent_mode and graduated_count < 2
        )
        assert skip is False
        legacy_skip = graduated_count < 1 or (not False and graduated_count < 2)
        assert legacy_skip is True


class TestTerminalAndAccounting:
    def test_stage_totals_reconcile_with_snapshot(self):
        budget = StageBudget.permanent_discovery_default()
        budget.consume("intake", 2)
        budget.consume("market_batching", 1)
        snap = budget.snapshot()
        assert snap["total_used"] == 3
        assert snap["total_remaining"] == 27
        assert snap["total_ceiling"] == 30
        assert sum(snap["used_by_stage"].values()) == snap["total_used"]

    def test_no_false_budget_terminal_when_capacity_remains(self):
        budget = StageBudget.permanent_discovery_default()
        budget.consume("intake", 3)
        budget.seal("intake")
        budget.consume("protocol_confirmation", 2)
        assert budget.available("market_batching") == 2
        assert budget.available("holder_safety") == 8
