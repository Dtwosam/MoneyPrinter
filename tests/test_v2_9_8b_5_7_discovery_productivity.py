"""V2-9.8B.5–7 discovery productivity repair focused proofs.

Disposable DBs and injected fixtures only. No production campaign, no live
network, no retrieval/financial activation.
"""

from __future__ import annotations

import base64
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from printer_v1.db import apply_migrations
from printer_v1.discovery.direct_migration_discovery import (
    run_direct_migration_discovery,
)
from printer_v1.discovery.graduated_liquidity_front_door import (
    BELOW_FLOOR_MARKET_COOLDOWN_SECONDS,
    LIQUIDITY_BELOW_SELECTION_FLOOR,
    LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN,
    LIQUIDITY_PROVEN,
    load_market_floor_state,
    market_floor_cooldown_active,
    record_market_floor_state,
    run_graduated_liquidity_front_door,
    LiquidityEvidence,
    select_two_eligible_tokens,
    combined_reserve_order,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.graduated_supply_front_door import (
    OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
    build_graduated_supply,
)
from printer_v1.operator_cli.holder_reliability_budget_control import (
    OPERATION_CEILING,
    build_ledger,
)
from printer_v1.operator_cli.operational_memory_factory_command import (
    EXPECTED_MIGRATION_COUNT,
    OPERATIONAL_GRADUATED_SUPPLY_KWARGS as PUBLIC_SUPPLY_KWARGS,
)
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pump_migration import prove_pump_migration_transaction
from printer_v1.sources import pump_migration as pm
from printer_v1.sources.pumpfun_direct import PUMP_PROGRAM_ID
from printer_v1.sources.pumpswap import PUMPSWAP_AMM_PROGRAM_ID, _b58decode
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    export_graduated_candidates,
    record_graduated_candidate,
)


NOW = "2026-07-26T18:00:00+00:00"
SEED = "v2-9-8b-5-7-productivity-seed"

# Six distinct mint/sig/pool triples (valid base58 32-byte identities).
_SPECS = [
    (
        "6wtZueu89AGwQkGUki3HcerjCDFxLA9PyVUBWQbMpump",
        "ijqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESaaaaaaa",
        "6TJuebvz9hqJaybCWpKm7ygmFqcxHxJ3Azi5BJhmHak",
    ),
    (
        "71pkkHscUWYPjLb6ZgU7X7iLh6Pkk86EbbgTWrPcAN3G",
        "kbqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESbbbbbbb",
        "AMiZNVbPaKVKeRgecW4GxKedmp72stFpQP65bBb79Lg",
    ),
    (
        "75kwavr6oror3vuiNetwRaZxByXZA635DhtjXJBrVpJi",
        "mcqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESccccccc",
        "EG8D6PFnzw9Lhsn6iBnnnfcWHnb7TpDbdmU614UT16c",
    ),
    (
        "79h8RZpb9D5JNXELBdKmL3RZgrfMa3yuqp71Xjz6qGaA",
        "ndqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESddddddd",
        "JAXrpGvCRYoMmKsYosXJd1aNom5C3kBNs9r6QwMnrrY",
    ),
    (
        "7DdKGCo5UZLkh7YwzbkbEWHBBjo9z1vkTvKHYBnMAiqc",
        "oeqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESeeeeeee",
        "N4wWYAabrATNpmxzuZFpTMYFKjZGdg9A6YE6ppF8icU",
    ),
    (
        "7HZW6qmZoucD1hsZoaBR8y8ngcvxPysb62XZYdabWB74",
        "pfqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESfffffff",
        "RyMAG4F1Gn7PtE4T1EzLHhW7qi3MDc6wKvc7Eh8UaNQ",
    ),
]


def _pool_acct(mint: str) -> dict:
    data = b"\x01" * 43 + _b58decode(mint) + b"\x02" * 226
    return {
        "owner": PUMPSWAP_AMM_PROGRAM_ID,
        "data": [base64.b64encode(data).decode(), "base64"],
    }


def _migration_tx(pool: str, mint: str, *, block_time: int = 1_784_000_000, slot: int = 400_000_000):
    return {
        "blockTime": block_time,
        "slot": slot,
        "transaction": {
            "message": {
                "accountKeys": [pool, mint, PUMP_PROGRAM_ID, PUMPSWAP_AMM_PROGRAM_ID]
            }
        },
        "meta": {"err": None, "loadedAddresses": {"writable": [], "readonly": []}},
    }


def _mock_rpc(by_sig: dict) -> None:
    def fake_rpc(rpc_url, method, params, *, timeout_seconds):
        if method == "getTransaction":
            sig = params[0]
            tx, _ = by_sig.get(sig, (None, {}))
            return {"result": tx}
        if method == "getMultipleAccounts":
            chunk = params[0]
            for _sig, (_tx, infos) in by_sig.items():
                if any(k in infos for k in chunk):
                    return {"result": {"value": [infos.get(k) for k in chunk]}}
            return {"result": {"value": [None for _ in chunk]}}
        return {"result": None}

    return fake_rpc


def _migration_transport(pairs: list[dict[str, str]]):
    def transport(context):
        return {
            "request_kind": "pumpfun_migration_stream",
            "source_name": "pumpportal",
            "tokens": [
                {
                    "mint": p["mint"],
                    "migration_signature": p["signature"],
                    "chain": "solana",
                    "poolSource": "pumpportal",
                }
                for p in pairs
            ],
        }

    return transport


def _round_robin_migration_transport(rounds: list[list[dict[str, str]]]):
    state = {"i": 0}

    def transport(context):
        idx = min(state["i"], len(rounds) - 1)
        state["i"] += 1
        pairs = rounds[idx]
        return {
            "request_kind": "pumpfun_migration_stream",
            "source_name": "pumpportal",
            "tokens": [
                {
                    "mint": p["mint"],
                    "migration_signature": p["signature"],
                    "chain": "solana",
                    "poolSource": "pumpportal",
                }
                for p in pairs
            ],
        }

    return transport, state


def _verifier_factory(by_sig: dict):
    def factory(mint: str, signature: str):
        def transport(context):
            # Use real verification path via patched RPC outside.
            from printer_v1.sources.pump_migration import (
                build_graduation_verifier_transport,
            )

            return build_graduation_verifier_transport(
                migration_signature=signature, expected_mint=mint
            )(context)

        return transport

    return factory


def _pair_payload(pool: str, mint: str, liquidity: float | None):
    return {
        "pairs": [
            {
                "chainId": "solana",
                "pairAddress": pool,
                "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
                "priceUsd": "0.10",
                "liquidity": ({} if liquidity is None else {"usd": liquidity}),
                "volume": {"m5": 100.0, "h1": 1000.0, "h24": 10000.0},
                "txns": {"m5": {"buys": 3, "sells": 2}},
                "priceChange": {"m5": 1.0},
                "marketCap": 50_000.0 if liquidity and liquidity >= 3000 else 5.0,
            }
        ]
    }


def _dex_factory(payload_by_pool: dict):
    def factory(mint, pool):
        return fixture_success_transport(payload_by_pool[pool])

    return factory


def _locked_counts(connection: sqlite3.Connection) -> dict[str, int]:
    out: dict[str, int] = {}
    for table in LOCKED_CAPABILITY_TABLES:
        try:
            out[table] = int(
                connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
            )
        except sqlite3.Error:
            out[table] = -1
    return out


class DiscoveryProductivityRepairTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "productivity.sqlite3"
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.locked_before = _locked_counts(self.connection)
        self.by_sig: dict = {}
        for mint, sig, pool in _SPECS:
            self.by_sig[sig] = (
                _migration_tx(pool, mint),
                {pool: _pool_acct(mint)},
            )
        self.rpc_patch = mock.patch.object(
            pm, "_rpc_post", side_effect=_mock_rpc(self.by_sig)
        )
        self.rpc_patch.start()

    def tearDown(self) -> None:
        self.rpc_patch.stop()
        self.connection.close()
        self.temp.cleanup()

    def test_shared_supply_kwargs_and_migration_count(self) -> None:
        self.assertEqual(PUBLIC_SUPPLY_KWARGS, OPERATIONAL_GRADUATED_SUPPLY_KWARGS)
        self.assertEqual(OPERATIONAL_GRADUATED_SUPPLY_KWARGS["collection_rounds"], 1)
        self.assertEqual(OPERATIONAL_GRADUATED_SUPPLY_KWARGS["max_candidates"], 5)
        self.assertEqual(
            OPERATIONAL_GRADUATED_SUPPLY_KWARGS["front_door_max_candidates"], 6
        )
        self.assertTrue(OPERATIONAL_GRADUATED_SUPPLY_KWARGS["run_locator"])
        from printer_v1.db.migrate import canonical_migration_count

        self.assertEqual(EXPECTED_MIGRATION_COUNT, canonical_migration_count())
        self.assertGreaterEqual(EXPECTED_MIGRATION_COUNT, 45)
        self.assertEqual(OPERATION_CEILING, 45)

    def test_five_distinct_migrations_confirm_up_to_five(self) -> None:
        pairs = [
            {"mint": mint, "signature": sig} for mint, sig, _pool in _SPECS[:5]
        ]
        report = run_direct_migration_discovery(
            self.db,
            migration_transport=_migration_transport(pairs),
            now=NOW,
            max_candidates=5,
            collection_rounds=1,
        )
        self.assertEqual(report["confirmed_count"], 5)
        self.assertEqual(len(export_graduated_candidates(self.connection)), 5)
        self.assertLessEqual(
            report["source_operation_ledger"]["source_requests"], 6
        )  # 1 migration + 5 verifies

    def test_fewer_candidates_honest_lower_count(self) -> None:
        pairs = [
            {"mint": _SPECS[0][0], "signature": _SPECS[0][1]},
            {"mint": _SPECS[1][0], "signature": _SPECS[1][1]},
        ]
        report = run_direct_migration_discovery(
            self.db,
            migration_transport=_migration_transport(pairs),
            now=NOW,
            max_candidates=5,
            collection_rounds=1,
        )
        self.assertEqual(report["confirmed_count"], 2)

    def test_cross_round_duplicates_do_not_consume_capacity_twice(self) -> None:
        pair = {"mint": _SPECS[0][0], "signature": _SPECS[0][1]}
        transport, state = _round_robin_migration_transport(
            [[pair], [pair], [pair]]
        )
        report = run_direct_migration_discovery(
            self.db,
            migration_transport=transport,
            now=NOW,
            max_candidates=5,
            collection_rounds=3,
        )
        self.assertEqual(state["i"], 3)
        self.assertEqual(report["migration_intake"]["collection_rounds"], 3)
        self.assertEqual(report["migration_intake"]["valid_pair_count"], 1)
        self.assertEqual(report["confirmed_count"], 1)
        # 3 migration rounds + 1 verify
        self.assertEqual(report["source_operation_ledger"]["source_requests"], 4)

    def test_conflicting_evidence_fails_closed(self) -> None:
        mint = _SPECS[0][0]
        sig_a = _SPECS[0][1]
        sig_b = _SPECS[1][1]
        report = run_direct_migration_discovery(
            self.db,
            migration_transport=_migration_transport(
                [
                    {"mint": mint, "signature": sig_a},
                    {"mint": mint, "signature": sig_b},
                ]
            ),
            now=NOW,
            max_candidates=5,
        )
        # First pair wins; conflicting second is not verified as a second mint.
        self.assertEqual(report["migration_intake"]["conflicting_count"], 1)
        self.assertEqual(report["confirmed_count"], 1)

    def test_exact_pumpswap_confirmation_required(self) -> None:
        mint, sig, pool = _SPECS[0]
        # Break confirmation by removing pool account ownership.
        self.by_sig[sig] = (
            _migration_tx(pool, mint),
            {pool: {"owner": "11111111111111111111111111111111", "data": ["", "base64"]}},
        )
        report = run_direct_migration_discovery(
            self.db,
            migration_transport=_migration_transport(
                [{"mint": mint, "signature": sig}]
            ),
            now=NOW,
            max_candidates=5,
        )
        self.assertEqual(report["confirmed_count"], 0)
        self.assertEqual(len(export_graduated_candidates(self.connection)), 0)

    def test_fresh_eligible_reserve_can_reach_six(self) -> None:
        for mint, sig, pool in _SPECS[:6]:
            record_graduated_candidate(
                self.connection,
                mint=mint,
                migration_signature=sig,
                pumpswap_pool=pool,
                graduation_block_time=1_784_000_000,
                graduation_slot=1,
                now=NOW,
                discovery_channel=LATEST_GRADUATED_CHANNEL,
            )
        self.connection.commit()
        payloads = {
            pool: _pair_payload(pool, mint, 10_000.0)
            for mint, _sig, pool in _SPECS[:6]
        }
        report = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED,
            latest_mints={m for m, _, _ in _SPECS[:3]},
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            max_candidates=6,
        )
        self.assertEqual(report["candidate_count"], 6)
        self.assertEqual(
            report["latest_eligible_count"] + report["persisted_eligible_count"], 6
        )
        self.assertEqual(len(report["combined_reserve_order"]), 6)
        self.assertEqual(report["market_calls"], 6)
        self.assertEqual(report["cooldown_skip_count"], 0)

    def test_below_floor_cooldown_skips_dex_and_reopens_after_expiry(self) -> None:
        mint, sig, pool = _SPECS[0]
        record_graduated_candidate(
            self.connection,
            mint=mint,
            migration_signature=sig,
            pumpswap_pool=pool,
            graduation_block_time=1_784_000_000,
            graduation_slot=1,
            now=NOW,
            discovery_channel=LATEST_GRADUATED_CHANNEL,
        )
        self.connection.commit()
        payloads_low = {pool: _pair_payload(pool, mint, 9.06)}
        first = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED,
            latest_mints={mint},
            dexscreener_transport_factory=_dex_factory(payloads_low),
            now=NOW,
            max_candidates=6,
        )
        self.assertEqual(first["market_calls"], 1)
        self.assertEqual(first["below_floor_count"], 1)
        self.assertEqual(first["candidates"][0]["rejection"], LIQUIDITY_BELOW_SELECTION_FLOOR)
        state = load_market_floor_state(self.connection, mint)
        self.assertIsNotNone(state)
        self.assertTrue(market_floor_cooldown_active(state, now=NOW))

        call_counter = {"n": 0}

        def counting_factory(m, p):
            call_counter["n"] += 1
            return fixture_success_transport(payloads_low[p])

        second = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED + "|2",
            latest_mints={mint},
            dexscreener_transport_factory=counting_factory,
            now=NOW,  # still inside cooldown
            max_candidates=6,
        )
        self.assertEqual(call_counter["n"], 0)
        self.assertEqual(second["market_calls"], 0)
        self.assertEqual(second["cooldown_skip_count"], 1)
        self.assertEqual(
            second["candidates"][0]["rejection"],
            LIQUIDITY_BELOW_SELECTION_FLOOR_COOLDOWN,
        )
        self.assertEqual(second["candidates"][0]["liquidity"]["liquidity_usd"], 9.06)

        later = (
            datetime.fromisoformat(NOW) + timedelta(seconds=BELOW_FLOOR_MARKET_COOLDOWN_SECONDS + 1)
        ).isoformat()
        payloads_high = {pool: _pair_payload(pool, mint, 12_000.0)}

        def high_factory(m, p):
            call_counter["n"] += 1
            return fixture_success_transport(payloads_high[p])

        third = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED + "|3",
            latest_mints={mint},
            dexscreener_transport_factory=high_factory,
            now=later,
            max_candidates=6,
        )
        self.assertGreaterEqual(call_counter["n"], 1)
        self.assertEqual(third["market_calls"], 1)
        self.assertEqual(third["cooldown_skip_count"], 0)
        self.assertTrue(third["candidates"][0]["eligible"])
        self.assertEqual(third["candidates"][0]["liquidity"]["status"], LIQUIDITY_PROVEN)

    def test_selection_stops_after_two_and_does_not_auto_activate_reserve(self) -> None:
        class Cand:
            def __init__(self, mint: str):
                self.mint = mint
                self.pumpswap_pool = f"pool-{mint[:4]}"
                self.market_identity = f"solana-mainnet:pumpswap:pool-{mint[:4]}"
                self.provenance = LATEST_GRADUATED_CHANNEL
                self.eligible = True
                self.rejection = None
                self.liquidity = LiquidityEvidence(
                    LIQUIDITY_PROVEN, 10_000.0, mint, self.pumpswap_pool,
                    "AT_OR_ABOVE_3000_FLOOR", "COMPLETE",
                )
                self.lifecycle_state = "PUMPSWAP_GRADUATED_CONFIRMED"
                self.graduation_block_time = 1

            def to_dict(self):
                return {
                    "mint": self.mint,
                    "pool": self.pumpswap_pool,
                    "market_identity": self.market_identity,
                    "provenance": self.provenance,
                    "eligible": True,
                }

        eligible = [Cand(f"mint{i}") for i in range(6)]
        order = combined_reserve_order(eligible, cycle_seed=SEED)
        self.assertEqual(len(order), 6)
        evaluated = {"n": 0}

        def holder_evaluator(candidate):
            evaluated["n"] += 1
            return True, ""

        result = select_two_eligible_tokens(
            eligible,
            cycle_seed=SEED,
            holder_evaluator=holder_evaluator,
            candidate_cap=5,
        )
        self.assertEqual(result["eligible_count"], 2)
        self.assertEqual(len(result["selected"]), 2)
        self.assertEqual(evaluated["n"], 2)
        self.assertEqual(result["terminal"], "SELECTION_TWO_TOKEN_READY")
        self.assertEqual(result["holder_operations"], 2)

    def test_deterministic_non_ranked_ordering(self) -> None:
        class Cand:
            def __init__(self, mint: str, liq: float):
                self.mint = mint
                self.pumpswap_pool = f"pool-{mint}"
                self.market_identity = f"id-{mint}"
                self.provenance = "LATEST_GRADUATED"
                self.lifecycle_state = "PUMPSWAP_GRADUATED_CONFIRMED"
                self.liquidity = type("L", (), {"liquidity_usd": liq})()

        high = Cand("aaa", 50_000.0)
        low = Cand("zzz", 3_001.0)
        a = combined_reserve_order([high, low], cycle_seed=SEED)
        b = combined_reserve_order([low, high], cycle_seed=SEED)
        self.assertEqual([c.mint for c in a], [c.mint for c in b])

    def test_stage_local_budget_under_ceiling_and_locked_tables(self) -> None:
        pairs = [
            {"mint": mint, "signature": sig} for mint, sig, _ in _SPECS[:5]
        ]
        discovery = run_direct_migration_discovery(
            self.db,
            migration_transport=_migration_transport(pairs),
            now=NOW,
            max_candidates=5,
            collection_rounds=3,
        )
        # With all pairs in first round, later rounds are empty but still charged.
        discovery_ops = int(discovery["source_operation_ledger"]["source_requests"])
        payloads = {
            pool: _pair_payload(pool, mint, 10_000.0)
            for mint, _sig, pool in _SPECS[:5]
        }
        front = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED,
            latest_mints={m for m, _, _ in _SPECS[:5]},
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            max_candidates=6,
        )
        market_ops = int(front["source_operation_ledger"]["liquidity_requests"])
        base = discovery_ops + market_ops
        ledger = build_ledger(
            pump_operations=0,
            additional_governed_operations=base,
            deadline_at=datetime.fromisoformat(NOW) + timedelta(seconds=1200),
        )
        self.assertLessEqual(ledger.charged_operations + 6, OPERATION_CEILING)
        self.assertEqual(ledger.operation_ceiling, 45)
        locked_after = _locked_counts(self.connection)
        self.assertEqual(locked_after, self.locked_before)
        integrity = self.connection.execute("PRAGMA integrity_check").fetchone()[0]
        self.assertEqual(integrity, "ok")

    def test_build_graduated_supply_uses_operational_bounds(self) -> None:
        pairs = [
            {"mint": mint, "signature": sig} for mint, sig, _ in _SPECS[:2]
        ]
        # Register a third below-floor persisted mint beforehand.
        mint3, sig3, pool3 = _SPECS[2]
        record_graduated_candidate(
            self.connection,
            mint=mint3,
            migration_signature=sig3,
            pumpswap_pool=pool3,
            graduation_block_time=1_784_000_000,
            graduation_slot=1,
            now=NOW,
            discovery_channel=LATEST_GRADUATED_CHANNEL,
        )
        self.connection.commit()

        payloads = {
            _SPECS[0][2]: _pair_payload(_SPECS[0][2], _SPECS[0][0], 12_000.0),
            _SPECS[1][2]: _pair_payload(_SPECS[1][2], _SPECS[1][0], 11_000.0),
            pool3: _pair_payload(pool3, mint3, 9.0),
        }

        def no_locator_transport(context):
            return {"pairs": []}

        supply = build_graduated_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_migration_transport(pairs),
            dexscreener_transport_factory=_dex_factory(payloads),
            locator_transport=no_locator_transport,
            now=NOW,
            **dict(OPERATIONAL_GRADUATED_SUPPLY_KWARGS),
            discovery_request_key_prefix="prod-supply",
            front_door_request_key_prefix="prod-market",
        )
        self.assertGreaterEqual(supply.diagnostics["confirmed_this_cycle"], 2)
        self.assertEqual(supply.diagnostics["front_door_liquidity_requests"], 3)
        self.assertTrue(supply.ready)
        self.assertGreaterEqual(len(supply.holder_reserve_supply), 2)
        # Unselected eligible reserves do not become activation by themselves.
        self.assertLessEqual(len(supply.graduated_supply), 2)


if __name__ == "__main__":
    unittest.main()
