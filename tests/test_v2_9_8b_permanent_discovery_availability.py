"""Focused offline proofs for permanent discovery availability.

Disposable SQLite and fixture payloads only. No provider contact, operational
campaign, readiness artifact, authorization, retrieval, decision, position,
trade, audit or PnL mutation.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sqlite3
import tempfile

import pytest

from printer_v1.contracts.enums import SourceStatus
from printer_v1.db import apply_migrations
from printer_v1.db import migrate as migration_runner
from printer_v1.discovery.permanent_discovery_availability import (
    BROAD_NOMINATED,
    CURRENT_POOL_CONFIRMED,
    CURRENT_VISIBLE,
    EXACT_POOL_NO_MATCH,
    FULLY_ELIGIBLE,
    MARKET_READY,
    NEW_POOL_PENDING_PROOF,
    POOL_RECONCILIATION_DUE,
    SOURCE_UNAVAILABLE,
    UNSUPPORTED_VENUE,
    CandidateObservation,
    ExactMarketObservation,
    StageBudget,
    freeze_eligible_reserve,
    interleave_candidate_observations,
    load_exact_market_states,
    merge_candidate_observations,
    order_canonical_inventory_fairly,
    record_exact_market_transition,
    reconcile_pool_identity,
    run_dexscreener_batch_market_resolution,
    run_geckoterminal_fresh_nomination,
    resolve_dexscreener_mint_batch,
    should_poll_exact_pool,
    upsert_reserve_layer,
)
from printer_v1.discovery.eligible_token_supply import (
    BUDGET_EXHAUSTION,
    GRADUATED_SUPPLY_READY,
    run_persistent_eligible_token_supply,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import (
    PUMPSWAP_AMM_PROGRAM_ID,
    PUMPSWAP_VENUE,
    record_graduated_candidate,
)
from printer_v1.sources import dexscreener as dexscreener_source
from printer_v1.sources import geckoterminal as geckoterminal_source
from printer_v1.sources.dexscreener import (
    build_dexscreener_mint_batch_transport,
    normalize_dexscreener_fixture_result,
)
from printer_v1.sources.geckoterminal import (
    build_geckoterminal_token_pools_transport,
    fixture_success_transport as geckoterminal_fixture_success_transport,
    normalize_geckoterminal_payload,
)


NOW = "2026-08-04T12:00:00+00:00"
LATER = "2026-08-04T12:30:00+00:00"
NETWORK = "solana-mainnet"
TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
POOL_PROGRAM = "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA"
WSOL = "So11111111111111111111111111111111111111112"


def _apply_through(db_path: Path, maximum_prefix: int) -> None:
    connection = sqlite3.connect(db_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            """CREATE TABLE IF NOT EXISTS printer_schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TEXT NOT NULL DEFAULT (datetime('now'))
            )"""
        )
        applied = {
            row[0]
            for row in connection.execute(
                "SELECT version FROM printer_schema_migrations"
            )
        }
        for path in sorted(migration_runner.MIGRATIONS_DIR.glob("*.sql")):
            if int(path.name.split("_", 1)[0]) > maximum_prefix:
                continue
            if path.name not in applied:
                connection.executescript(path.read_text(encoding="utf-8"))
                connection.execute(
                    "INSERT INTO printer_schema_migrations(version) VALUES (?)",
                    (path.name,),
                )
        connection.commit()
    finally:
        connection.close()


@pytest.fixture
def database():
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "permanent.sqlite3"
        apply_migrations(path)
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield path, connection
        finally:
            connection.close()


def _market(
    mint: str = "MintA",
    pool: str = "PoolA",
    *,
    state: str = CURRENT_VISIBLE,
    reason: str = "EXACT_PROVIDER_ROW",
    next_action: str | None = None,
    observed_at: str = NOW,
) -> ExactMarketObservation:
    return ExactMarketObservation(
        network=NETWORK,
        mint=mint,
        pool=pool,
        token_program=TOKEN_PROGRAM,
        pool_program=POOL_PROGRAM,
        base_mint=mint,
        quote_mint=WSOL,
        venue="pumpswap",
        state=state,
        reason=reason,
        observed_at=observed_at,
        next_lawful_action_at=next_action,
        source_provenance={"source": "dexscreener", "request_id": 7},
        contract_version="DEXSCREENER_TOKENS_V1_2026_08_04",
    )


class TestMigration051:
    def test_fresh_migration_creates_projection_history_and_reserve(self, database):
        _, connection = database
        names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        assert {
            "printer_exact_market_states",
            "printer_exact_market_state_transitions",
            "printer_discovery_reserve_layers",
        } <= names
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []

    def test_upgrade_from_050_applies_forward_cleanly(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "upgrade.sqlite3"
            _apply_through(path, 50)
            before = sqlite3.connect(path).execute(
                "SELECT COUNT(*) FROM printer_schema_migrations"
            ).fetchone()[0]
            apply_migrations(path)
            connection = sqlite3.connect(path)
            try:
                versions = [
                    row[0]
                    for row in connection.execute(
                        "SELECT version FROM printer_schema_migrations ORDER BY version"
                    )
                ]
                assert before == 50
                assert versions[-1] == "051_permanent_discovery_availability.sql"
                assert len(versions) == 51
                assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
                assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
            finally:
                connection.close()


class TestCanonicalBatchMarketOwner:
    @staticmethod
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
            rows.append(
                {
                    "mint_identity": mint,
                    "pumpswap_pool": pool,
                    "market_identity": f"solana-mainnet:{PUMPSWAP_VENUE}:{pool}",
                    "lifecycle_state": "PUMPSWAP_GRADUATED_CONFIRMED",
                    "graduation_block_time": 1_700_000_000 + index,
                    "pumpswap_program_id": PUMPSWAP_AMM_PROGRAM_ID,
                    "latest_channel": "PERSISTED_GRADUATED",
                }
            )
        connection.commit()
        return rows

    def test_one_batch_resolves_four_exact_pools_and_persists_market_ready(self, database):
        _, connection = database
        inventory = self._seed(connection)
        calls = []

        def transport(context):
            calls.append(tuple(context.request.payload["token_mints"]))
            return {
                "pairs": [
                    {
                        "chainId": "solana",
                        "pairAddress": row["pumpswap_pool"],
                        "dexId": "pumpswap",
                        "baseToken": {"address": row["mint_identity"]},
                        "quoteToken": {"address": WSOL},
                        "liquidity": {"usd": 4_000 + index},
                    }
                    for index, row in enumerate(reversed(inventory))
                ]
            }

        result = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="batch-four",
            now=NOW,
            campaign_id="campaign-a",
        )

        assert len(calls) == 1
        assert calls[0] == tuple(sorted(row["mint_identity"] for row in inventory))
        assert result["batch_sizes"] == [4]
        assert result["calls_by_stage"] == {
            "market_batching": 1,
            "reconciliation": 0,
        }
        assert len(result["source_request_ids"]) == 1
        assert len(result["source_response_ids"]) == 1
        assert result["source_failure_ids"] == []
        assert result["market_ready_count"] == 4
        assert {item["mint"] for item in result["candidates"] if item["eligible"]} == {
            row["mint_identity"] for row in inventory
        }
        assert connection.execute(
            "SELECT COUNT(*) FROM printer_discovery_reserve_layers WHERE reserve_layer=?",
            (MARKET_READY,),
        ).fetchone()[0] == 4

    def test_no_match_is_absence_then_suppresses_repeat_until_due(self, database):
        _, connection = database
        inventory = self._seed(connection, 1)
        calls = []

        def transport(context):
            calls.append(context.request.request_key)
            return {"pairs": []}

        first = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="no-match-first",
            now=NOW,
            campaign_id="campaign-a",
        )
        second = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=transport,
            request_key="no-match-second",
            now="2026-08-04T12:05:00+00:00",
            campaign_id="campaign-b",
        )

        assert calls == ["no-match-first"]
        assert first["reconciliation_due_count"] == 1
        assert first["provider_failures"] == 0
        assert second["batch_sizes"] == []
        assert second["suppressed_exact_pool_count"] == 1
        state = load_exact_market_states(connection, mint="Mint00")[0]
        assert state["current_state"] == EXACT_POOL_NO_MATCH
        assert state["no_match_count"] == 1

    def test_different_pool_is_pending_and_never_substituted(self, database):
        _, connection = database
        inventory = self._seed(connection, 1)
        result = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=fixture_success_transport(
                {
                    "pairs": [{
                        "chainId": "solana",
                        "pairAddress": "DifferentPool",
                        "dexId": "pumpswap",
                        "baseToken": {"address": "Mint00"},
                        "quoteToken": {"address": WSOL},
                        "liquidity": {"usd": 99_000},
                    }]
                }
            ),
            request_key="changed-pool",
            now=NOW,
            campaign_id="campaign-a",
        )
        assert result["market_ready_count"] == 0
        assert result["reconciliation_outcomes"] == [{
            "mint": "Mint00",
            "historical_pool": "Pool00",
            "observed_pool": "DifferentPool",
            "state": NEW_POOL_PENDING_PROOF,
            "reason": "DIFFERENT_POOL_REQUIRES_EXACT_PROOF",
        }]
        assert {row["pool_address"] for row in load_exact_market_states(connection, mint="Mint00")} == {
            "Pool00", "DifferentPool"
        }

    def test_unresolved_mint_cascades_to_geckoterminal_same_pool(self, database):
        _, connection = database
        inventory = self._seed(connection, 1)
        gt_calls = []

        def gt_factory(mint):
            gt_calls.append(mint)
            return geckoterminal_fixture_success_transport(
                {
                    "data": [{
                        "id": "solana_Pool00",
                        "type": "pool",
                        "attributes": {
                            "address": "Pool00",
                            "base_token_address": mint,
                            "quote_token_address": WSOL,
                            "dex_id": "pumpswap",
                            "reserve_in_usd": "6000",
                        },
                    }]
                }
            )

        result = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=fixture_success_transport({"pairs": []}),
            geckoterminal_transport_factory=gt_factory,
            enable_geckoterminal_fallback=True,
            request_key="mint-fallback",
            now=NOW,
            campaign_id="campaign-a",
        )
        assert gt_calls == ["Mint00"]
        assert result["calls_by_stage"] == {
            "market_batching": 1,
            "reconciliation": 1,
        }
        assert result["source_request_count"] == 2
        assert len(result["source_request_ids"]) == 2
        assert result["market_ready_count"] == 1
        assert result["candidates"][0]["eligible"] is True
        assert load_exact_market_states(connection, mint="Mint00")[0]["current_state"] == CURRENT_POOL_CONFIRMED

    def test_provider_failure_is_not_market_absence(self, database):
        _, connection = database
        inventory = self._seed(connection, 1)

        def broken(_context):
            raise RuntimeError("offline")

        result = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=broken,
            request_key="provider-failure",
            now=NOW,
            campaign_id="campaign-a",
        )
        assert result["provider_failures"] == 1
        assert result["reconciliation_due_count"] == 0
        assert load_exact_market_states(connection, mint="Mint00")[0]["current_state"] == SOURCE_UNAVAILABLE

    def test_due_same_pool_reappearance_records_queue_and_revival_transitions(self, database):
        _, connection = database
        inventory = self._seed(connection, 1)
        run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=fixture_success_transport({"pairs": []}),
            request_key="disappear",
            now=NOW,
            campaign_id="campaign-a",
        )
        restored = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=fixture_success_transport(
                {"pairs": [{
                    "chainId": "solana",
                    "pairAddress": "Pool00",
                    "dexId": "pumpswap",
                    "baseToken": {"address": "Mint00"},
                    "quoteToken": {"address": WSOL},
                    "liquidity": {"usd": 7_000},
                }]}
            ),
            request_key="reappear",
            now="2026-08-04T12:30:00+00:00",
            campaign_id="campaign-b",
        )
        assert restored["market_ready_count"] == 1
        transitions = [
            row[0]
            for row in connection.execute(
                "SELECT new_state FROM printer_exact_market_state_transitions ORDER BY transition_id"
            )
        ]
        assert transitions == [
            EXACT_POOL_NO_MATCH,
            POOL_RECONCILIATION_DUE,
            "SAME_POOL_REOBSERVED",
            CURRENT_POOL_CONFIRMED,
        ]

    @pytest.mark.parametrize(
        ("venue", "quote", "expected_state"),
        [
            ("unsupported-dex", WSOL, UNSUPPORTED_VENUE),
            ("pumpswap", "UnknownQuote", "CONTRACT_BLOCKED"),
        ],
    )
    def test_exact_pool_requires_supported_venue_and_quote_contract(
        self, database, venue, quote, expected_state
    ):
        _, connection = database
        inventory = self._seed(connection, 1)
        result = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=fixture_success_transport(
                {"pairs": [{
                    "chainId": "solana",
                    "pairAddress": "Pool00",
                    "dexId": venue,
                    "baseToken": {"address": "Mint00"},
                    "quoteToken": {"address": quote},
                    "liquidity": {"usd": 50_000},
                }]}
            ),
            request_key=f"contract-{expected_state}",
            now=NOW,
            campaign_id="campaign-a",
        )
        assert result["market_ready_count"] == 0
        assert result["candidates"][0]["eligible"] is False
        assert load_exact_market_states(connection, mint="Mint00")[0]["current_state"] == expected_state


class TestProductionSupplyComposition:
    @staticmethod
    def _empty_migration_transport():
        from printer_v1.sources.direct_pump_migration import (
            SIGNATURE_PAGE_REQUEST_KIND,
            TRANSACTION_REQUEST_KIND,
        )

        def transport(context):
            if context.request.request_kind == SIGNATURE_PAGE_REQUEST_KIND:
                return {"result": []}
            if context.request.request_kind == TRANSACTION_REQUEST_KIND:
                return {"result": None}
            raise AssertionError(context.request.request_kind)

        return transport

    def test_permanent_owner_builds_four_market_ready_in_one_batch(self, database):
        db_path, connection = database
        inventory = TestCanonicalBatchMarketOwner._seed(connection)
        locked_tables = (
            "printer_memory_retrieval_queries",
            "printer_memory_retrieval_matches",
            "printer_paper_decisions",
            "printer_paper_positions",
            "printer_paper_trade_events",
            "printer_paper_trade_audits",
        )
        before = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in locked_tables
        }
        pools = {row["mint_identity"]: row["pumpswap_pool"] for row in inventory}
        batch_calls = []

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
                        for mint in reversed(tuple(mints))
                    ]
                }
            )

        result = run_persistent_eligible_token_supply(
            db_path,
            cycle_seed="permanent-owner-seed",
            migration_transport=self._empty_migration_transport(),
            dexscreener_batch_transport_factory=batch_factory,
            now=NOW,
            collection_rounds=1,
            max_candidates=1,
            run_locator=False,
            required_token_capacity=2,
            permanent_availability=True,
            campaign_id="campaign-a",
        )

        assert result.ready is True
        assert result.terminal == GRADUATED_SUPPLY_READY
        assert len(result.eligible_reserve) == 4
        assert batch_calls == [tuple(sorted(pools))]
        assert result.diagnostics["required_token_capacity"] == 4
        after = {
            table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            for table in locked_tables
        }
        assert after == before

    def test_lawful_unexplored_work_never_becomes_universe_exhaustion(self, database):
        db_path, connection = database
        inventory = TestCanonicalBatchMarketOwner._seed(connection, 31)
        pools = {row["mint_identity"]: row["pumpswap_pool"] for row in inventory}

        def batch_factory(mints):
            return fixture_success_transport(
                {
                    "pairs": [{
                        "chainId": "solana",
                        "pairAddress": pools[mint],
                        "dexId": "pumpswap",
                        "baseToken": {"address": mint},
                        "quoteToken": {"address": WSOL},
                        "liquidity": {"usd": 2_999},
                    } for mint in mints]
                }
            )

        result = run_persistent_eligible_token_supply(
            db_path,
            cycle_seed="unexplored-seed",
            migration_transport=self._empty_migration_transport(),
            dexscreener_batch_transport_factory=batch_factory,
            now=NOW,
            run_locator=False,
            permanent_availability=True,
            enable_geckoterminal_reconciliation=False,
            campaign_id="campaign-unexplored",
        )
        assert result.ready is False
        assert result.shortage_classification == BUDGET_EXHAUSTION
        assert result.diagnostics["unexplored_unique_remaining"] == 1
        assert result.diagnostics["last_stop_reason"] == "DISCOVERY_OPERATION_BUDGET_EXHAUSTED"

    def test_geckoterminal_fresh_pool_enters_only_broad_reserve(self, database):
        _, connection = database
        report = run_geckoterminal_fresh_nomination(
            connection,
            request_key="gt-fresh",
            now=NOW,
            campaign_id="campaign-a",
            run_id="run-a",
            cycle_id="cycle-a",
            transport=geckoterminal_fixture_success_transport(
                {
                    "data": [{
                        "id": "solana_FreshPool",
                        "type": "pool",
                        "attributes": {
                            "address": "FreshPool",
                            "base_token_address": "FreshMint",
                            "quote_token_address": WSOL,
                            "dex_id": "pumpswap",
                            "reserve_in_usd": "9000",
                        },
                    }]
                }
            ),
        )
        assert report["nominations"] == [{
            "mint": "FreshMint", "pool": "FreshPool", "source": "geckoterminal"
        }]
        layers = connection.execute(
            "SELECT reserve_layer FROM printer_discovery_reserve_layers"
        ).fetchall()
        assert [row[0] for row in layers] == [BROAD_NOMINATED]
        assert load_exact_market_states(connection, mint="FreshMint")[0]["current_state"] == "CONTRACT_BLOCKED"

    def test_production_inventory_interleaves_all_five_categories(self, database):
        _, connection = database
        rows = TestCanonicalBatchMarketOwner._seed(connection, 5)
        record_exact_market_transition(
            connection,
            _market(
                mint="Mint03",
                pool="Pool03",
                state=POOL_RECONCILIATION_DUE,
                next_action=NOW,
            ),
            now=NOW,
        )
        record_exact_market_transition(
            connection,
            _market(mint="Mint04", pool="Pool04", state=CURRENT_VISIBLE),
            now=NOW,
        )
        connection.commit()
        ordered = order_canonical_inventory_fairly(
            connection,
            inventory_rows=rows,
            latest_mints=["Mint01"],
            fresh_mints=["Mint00"],
            now=NOW,
        )
        assert [row["mint_identity"] for row in ordered] == [
            "Mint00", "Mint01", "Mint02", "Mint03", "Mint04"
        ]

    def test_historical_pool_identity_and_transition_history_are_immutable(self, database):
        _, connection = database
        record_exact_market_transition(connection, _market(), now=NOW)
        record_exact_market_transition(
            connection,
            _market(pool="PoolB", state=NEW_POOL_PENDING_PROOF),
            now=LATER,
        )
        connection.commit()
        rows = load_exact_market_states(connection, mint="MintA")
        assert {row["pool_address"] for row in rows} == {"PoolA", "PoolB"}
        history = connection.execute(
            "SELECT transition_id FROM printer_exact_market_state_transitions"
        ).fetchall()
        assert len(history) == 2
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute(
                "UPDATE printer_exact_market_state_transitions SET reason_code='x'"
            )
        with pytest.raises(sqlite3.IntegrityError):
            connection.execute("DELETE FROM printer_exact_market_state_transitions")

    def test_resolved_program_identity_conflict_is_categorical_not_overwritten(self, database):
        _, connection = database
        record_exact_market_transition(connection, _market(), now=NOW)
        conflict = _market(state=CURRENT_VISIBLE)
        conflict = ExactMarketObservation(
            **{
                **conflict.__dict__,
                "pool_program": "ConflictingProgram",
                "reason": "CONFLICTING_OBSERVATION",
            }
        )
        record_exact_market_transition(connection, conflict, now=LATER)
        row = load_exact_market_states(connection, mint="MintA")[0]
        assert row["pool_program_id"] == POOL_PROGRAM
        assert row["current_state"] == "IDENTITY_CONFLICT"

    def test_three_reserve_layers_are_exact_mint_pool_and_evidence_bounded(self, database):
        _, connection = database
        record_exact_market_transition(connection, _market(), now=NOW)
        for layer in (BROAD_NOMINATED, MARKET_READY, FULLY_ELIGIBLE):
            upsert_reserve_layer(
                connection,
                network=NETWORK,
                mint="MintA",
                pool="PoolA",
                layer=layer,
                reserve_state="ACTIVE",
                reason="TEST_PASS",
                observed_at=NOW,
                next_lawful_action_at=LATER,
                evidence_expires_at=LATER,
                source_provenance={"source": "fixture"},
                evidence={"categorical_gate": "PASS"},
                campaign_id="campaign-a",
            )
        connection.commit()
        rows = connection.execute(
            "SELECT reserve_layer FROM printer_discovery_reserve_layers ORDER BY reserve_layer"
        ).fetchall()
        assert {row[0] for row in rows} == {
            BROAD_NOMINATED,
            MARKET_READY,
            FULLY_ELIGIBLE,
        }


class TestPermanentStatePolicy:
    def test_exact_no_match_suppresses_repeat_until_reconciliation_boundary(self, database):
        _, connection = database
        record_exact_market_transition(connection, _market(), now=NOW)
        due = "2026-08-04T13:00:00+00:00"
        record_exact_market_transition(
            connection,
            _market(
                state=EXACT_POOL_NO_MATCH,
                reason="LAWFUL_HTTP_200_EMPTY",
                next_action=due,
                observed_at="2026-08-04T12:01:00+00:00",
            ),
            now="2026-08-04T12:01:00+00:00",
        )
        connection.commit()
        row = load_exact_market_states(connection, mint="MintA")[0]
        assert row["current_state"] == EXACT_POOL_NO_MATCH
        assert row["no_match_streak"] == 1
        assert should_poll_exact_pool(row, at="2026-08-04T12:59:59+00:00") is False
        assert should_poll_exact_pool(row, at=due) is True
        record_exact_market_transition(
            connection,
            _market(
                state=POOL_RECONCILIATION_DUE,
                reason="NEXT_LAWFUL_BOUNDARY_REACHED",
                observed_at=due,
            ),
            now=due,
        )
        assert load_exact_market_states(connection, mint="MintA")[0][
            "current_state"
        ] == POOL_RECONCILIATION_DUE

    def test_same_pool_reappearance_and_different_pool_require_distinct_proof(self):
        same = reconcile_pool_identity(
            mint="MintA",
            historical_pool="PoolA",
            observed_pool="PoolA",
            exact_identity=True,
            supported_contract=True,
            protocol_confirmed=False,
        )
        changed = reconcile_pool_identity(
            mint="MintA",
            historical_pool="PoolA",
            observed_pool="PoolB",
            exact_identity=True,
            supported_contract=True,
            protocol_confirmed=False,
        )
        proved = reconcile_pool_identity(
            mint="MintA",
            historical_pool="PoolA",
            observed_pool="PoolB",
            exact_identity=True,
            supported_contract=True,
            protocol_confirmed=True,
        )
        assert same.state == "SAME_POOL_REOBSERVED"
        assert changed.state == NEW_POOL_PENDING_PROOF
        assert proved.state == CURRENT_POOL_CONFIRMED

    def test_fair_traversal_is_categorical_oldest_due_with_stable_ties(self):
        observations = [
            CandidateObservation("DUE_PERSISTED", "MintD2", "PoolD2", "s", "2026-08-04T10:01:00+00:00"),
            CandidateObservation("FRESH_NOMINATION", "MintF2", "PoolF2", "s", "2026-08-04T10:01:00+00:00"),
            CandidateObservation("DIRECT_MIGRATION", "MintM", "PoolM", "s", "2026-08-04T10:00:00+00:00"),
            CandidateObservation("FRESH_NOMINATION", "MintF1", "PoolF1", "s", "2026-08-04T10:00:00+00:00"),
            CandidateObservation("POOL_RECONCILIATION", "MintR", "PoolR", "s", "2026-08-04T10:00:00+00:00"),
            CandidateObservation("REVIVAL_OR_DISTINCT_EVIDENCE", "MintV", "PoolV", "s", "2026-08-04T10:00:00+00:00"),
            CandidateObservation("DUE_PERSISTED", "MintD1", "PoolD1", "s", "2026-08-04T10:00:00+00:00"),
        ]
        ordered = interleave_candidate_observations(observations)
        assert [item.mint for item in ordered] == [
            "MintF1", "MintM", "MintD1", "MintR", "MintV", "MintF2", "MintD2"
        ]

    def test_stage_budget_protects_later_capacity_and_flows_only_forward(self):
        budget = StageBudget.permanent_discovery_default()
        assert budget.total_ceiling == 30
        budget.consume("intake", 3)
        with pytest.raises(ValueError, match="STAGE_RESERVATION_EXCEEDED"):
            budget.consume("intake", 1)
        budget.consume("market_batching", 1)
        budget.advance("reconciliation")
        # One unused market-batching operation may now flow forward.
        budget.consume("reconciliation", 7)
        assert budget.used_by_stage["reconciliation"] == 7
        # Holder/safety and handoff reservations remain protected.
        assert budget.protected_remaining("holder_safety") == 8
        assert budget.protected_remaining("final_refresh_handoff") == 4


class TestMintBatchAndReserve:
    @staticmethod
    def _pair(mint: str, pool: str, liquidity: float, dex_id: str = "pumpfun"):
        return {
            "chain": "solana",
            "candidate_mint": mint,
            "token_mint": mint,
            "pair_address": pool,
            "base_mint": mint,
            "quote_mint": WSOL,
            "dex_id": dex_id,
            "liquidity_usd": liquidity,
            "txns_5m": 4,
            "volume_5m": 10.0,
        }

    def test_batch_resolution_accepts_30_mints_and_preserves_all_pool_identities(self):
        mints = [f"Mint{i:02d}" for i in range(30)]
        pairs = [
            self._pair(mint, f"Pool{i:02d}B", 99_000.0)
            for i, mint in reversed(list(enumerate(mints)))
        ]
        pairs.append(self._pair("Mint00", "Pool00A", 3_500.0))
        result = resolve_dexscreener_mint_batch(mints, pairs, observed_at=NOW)
        assert result.batch_size == 30
        assert set(result.by_mint) == set(mints)
        assert {row.pool for row in result.by_mint["Mint00"]} == {
            "Pool00A",
            "Pool00B",
        }
        # Provider order and liquidity do not choose a canonical pool.
        assert result.current_pool_by_mint == {}

    def test_multi_source_merge_preserves_provenance_and_disagreement(self):
        observations = [
            CandidateObservation("FRESH_NOMINATION", "MintA", "PoolA", "dexscreener", NOW),
            CandidateObservation("FRESH_NOMINATION", "MintA", "PoolA", "geckoterminal", LATER),
            CandidateObservation("POOL_RECONCILIATION", "MintA", "PoolB", "geckoterminal", LATER),
        ]
        merged = merge_candidate_observations(observations)
        assert set(merged["MintA"].pools) == {"PoolA", "PoolB"}
        assert set(merged["MintA"].sources) == {"dexscreener", "geckoterminal"}
        assert merged["MintA"].identity_disagreement is True

    def test_canonical_broad_reserve_retains_each_source_observation(self, database):
        _, connection = database
        observation = {
            "mint": "MintA",
            "pool": "PoolA",
            "base_mint": "MintA",
            "quote_mint": WSOL,
            "venue": "pumpswap",
        }
        from printer_v1.discovery.permanent_discovery_availability import (
            record_fresh_pool_nominations,
        )

        record_fresh_pool_nominations(
            connection,
            observations=[observation],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="campaign-a",
        )
        record_fresh_pool_nominations(
            connection,
            observations=[observation],
            source="geckoterminal",
            request_id=2,
            now=LATER,
            campaign_id="campaign-a",
        )
        raw = connection.execute(
            """SELECT source_provenance_json
               FROM printer_discovery_reserve_layers
               WHERE mint_identity='MintA' AND pool_address='PoolA'
                 AND reserve_layer=?""",
            (BROAD_NOMINATED,),
        ).fetchone()[0]
        observations = json.loads(raw)["observations"]
        assert {item["source"] for item in observations} == {
            "dexscreener", "geckoterminal"
        }

    def test_blocked_fresh_projection_resolves_once_to_exact_contract(self, database):
        _, connection = database
        from printer_v1.discovery.permanent_discovery_availability import (
            record_fresh_pool_nominations,
        )

        record_fresh_pool_nominations(
            connection,
            observations=[{
                "mint": "Mint00",
                "pool": "Pool00",
                "base_mint": "Mint00",
                "quote_mint": WSOL,
                "venue": "pumpswap",
            }],
            source="dexscreener",
            request_id=1,
            now=NOW,
            campaign_id="campaign-a",
        )
        inventory = TestCanonicalBatchMarketOwner._seed(connection, 1)
        result = run_dexscreener_batch_market_resolution(
            connection,
            inventory_rows=inventory,
            transport=fixture_success_transport(
                {"pairs": [{
                    "chainId": "solana",
                    "pairAddress": "Pool00",
                    "dexId": "pumpswap",
                    "baseToken": {"address": "Mint00"},
                    "quoteToken": {"address": WSOL},
                    "liquidity": {"usd": 8_000},
                }]}
            ),
            request_key="resolve-fresh-contract",
            now=LATER,
            campaign_id="campaign-a",
        )
        assert result["market_ready_count"] == 1
        row = load_exact_market_states(connection, mint="Mint00")[0]
        assert row["token_program_id"] == TOKEN_PROGRAM
        assert row["pool_program_id"] == POOL_PROGRAM

    def test_four_candidate_freeze_selects_two_and_retains_two_fresh_alternates(self):
        candidates = [
            {
                "mint": f"Mint{i}",
                "pool": f"Pool{i}",
                "fully_eligible": True,
                "evidence_expires_at": "2026-08-04T13:00:00+00:00",
            }
            for i in range(4)
        ]
        frozen = freeze_eligible_reserve(candidates, cycle_seed="neutral-seed", at=NOW)
        assert len(frozen.selected) == 2
        assert len(frozen.alternates) == 2
        assert len({item["mint"] for item in frozen.selected + frozen.alternates}) == 4

    def test_stale_alternate_is_rejected_before_activation(self):
        candidates = [
            {
                "mint": f"Mint{i}",
                "pool": f"Pool{i}",
                "fully_eligible": True,
                "evidence_expires_at": (
                    "2026-08-04T11:59:59+00:00"
                    if i == 3
                    else "2026-08-04T13:00:00+00:00"
                ),
            }
            for i in range(4)
        ]
        frozen = freeze_eligible_reserve(candidates, cycle_seed="neutral-seed", at=NOW)
        assert len(frozen.selected) == 2
        assert len(frozen.alternates) == 1
        assert [item["mint"] for item in frozen.rejected_stale] == ["Mint3"]


class TestGovernedBatchTransports:
    def test_dex_transport_deduplicates_stably_and_uses_one_30_mint_request(
        self, monkeypatch
    ):
        calls: list[str] = []

        def fake_get(endpoint, timeout_seconds, *, byte_ceiling):
            del timeout_seconds, byte_ceiling
            calls.append(endpoint)
            return [], 2

        monkeypatch.setattr(
            dexscreener_source, "_dexscreener_http_get_json", fake_get
        )
        mints = [f"Mint{i:02d}" for i in reversed(range(30))] + ["Mint00"]
        payload = build_dexscreener_mint_batch_transport(mints)(None)
        assert len(calls) == 1
        encoded = calls[0].rsplit("/", 1)[-1].split(",")
        assert encoded == sorted(set(mints))
        assert len(encoded) == 30
        assert payload["pairs"] == []
        assert payload["_requested_token_mints"] == sorted(set(mints))
        assert payload["transport_operations_used"] == 1

    def test_dex_transport_rejects_more_than_30_before_network(self):
        with pytest.raises(ValueError, match="DEXSCREENER_BATCH_SIZE_OUT_OF_CONTRACT"):
            build_dexscreener_mint_batch_transport(
                [f"Mint{i:02d}" for i in range(31)]
            )

    def test_successful_empty_dex_batch_is_market_absence_not_provider_failure(self):
        result = normalize_dexscreener_fixture_result(
            {"pairs": [], "_source_status_code": 200},
            request_kind="candidate_market_batch",
            requested_token_mints=("MintA",),
        )
        assert result.source_status == SourceStatus.COMPLETE
        assert result.failure_type is None
        assert result.normalized_payload["no_matching_pairs"] is True

    def test_gecko_token_pool_transport_is_exact_mint_bound_and_one_attempt(
        self, monkeypatch
    ):
        calls: list[str] = []

        def fake_load(endpoint, *, timeout_seconds):
            del timeout_seconds
            calls.append(endpoint)
            return {"data": []}

        monkeypatch.setattr(geckoterminal_source, "_load_public_json", fake_load)

        class Request:
            payload = {"token_mint": "MintA"}

        class Context:
            request = Request()

        payload = build_geckoterminal_token_pools_transport("MintA")(Context())
        assert len(calls) == 1
        assert "/networks/solana/tokens/MintA/pools" in calls[0]
        assert payload["_requested_token_mint"] == "MintA"

    def test_successful_empty_gecko_resolution_is_absence_not_source_failure(self):
        absent = normalize_geckoterminal_payload(
            {
                "data": [],
                "_source_status_code": 200,
                "_requested_token_mint": "MintA",
            },
            request_kind="candidate_market_batch",
            expected_token_mint="MintA",
        )
        failed = normalize_geckoterminal_payload(
            {
                "fixture_status": "failure",
                "failure_type": "geckoterminal_transport_failure",
                "failure_message": "offline",
            },
            request_kind="candidate_market_batch",
            expected_token_mint="MintA",
        )
        assert absent.source_status == SourceStatus.COMPLETE
        assert absent.failure_type is None
        assert absent.normalized_payload["no_matching_pools"] is True
        assert failed.source_status == SourceStatus.FAILED
        assert failed.failure_type == "geckoterminal_transport_failure"
