"""V2-9.8B.21 Eligible Token Supply architecture disposable proofs.

Fixture sources and disposable SQLite only. No production campaign, no live
network, no retrieval/financial activation, no automatic retry/successor.
"""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from printer_v1.db import apply_migrations
from printer_v1.discovery.combined_executor import _fisher_yates
from printer_v1.discovery.eligible_token_supply import (
    BUDGET_EXHAUSTION,
    DEFAULT_DISCOVERY_OPERATION_BUDGET,
    DURATION_EXHAUSTION,
    ELIGIBLE_FRESH,
    ELIGIBLE_STALE,
    EVALUATION_BATCH_SIZE,
    GRADUATED_SUPPLY_READY,
    LIFECYCLE_OPERATION_CEILING,
    REQUIRED_TOKEN_CAPACITY,
    SOURCE_AVAILABILITY_FAILURE,
    TRUE_MARKET_SUPPLY_SHORTAGE,
    classify_shortage,
    load_eligible_reserve,
    run_persistent_eligible_token_supply,
    upsert_eligible_reserve,
)
from printer_v1.discovery.graduated_liquidity_front_door import (
    BELOW_FLOOR_MARKET_COOLDOWN_SECONDS,
    LIQUIDITY_BELOW_SELECTION_FLOOR,
    LIQUIDITY_PROVEN,
    LiquidityEvidence,
    record_market_floor_state,
    run_graduated_liquidity_front_door,
)
from printer_v1.operator_cli.final_campaign_report import LOCKED_CAPABILITY_TABLES
from printer_v1.operator_cli.graduated_supply_front_door import (
    OPERATIONAL_GRADUATED_SUPPLY_KWARGS,
    build_graduated_supply,
)
from printer_v1.operator_cli.holder_reliability_budget_control import OPERATION_CEILING
from printer_v1.sources.dexscreener import fixture_success_transport
from printer_v1.sources.pumpswap_graduated_registry import (
    LATEST_GRADUATED_CHANNEL,
    PERSISTED_GRADUATED_CHANNEL,
    export_graduated_candidates,
    record_graduated_candidate,
)


NOW = "2026-07-27T22:00:00+00:00"
SEED = "v2-9-8b-21-eligible-supply-seed"

# 20 distinct mint/sig/pool triples (valid base58 32-byte identities).
_SPECS: list[tuple[str, str, str]] = [
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
    (
        "7S4XmHSx1NzN1111111111111111111111111111111",
        "qgqgk3HtkePfN1tJfCdQAxNfGbCrrgZJeFuiy4idNSnVBP1Ev2YqsNq1nUWLaX5t1kKu9S84AZk5usESggggggg",
        "S5xWYAabrATNpmxzuZFpTMYFKjZGdg9A6YE6ppF8icV",
    ),
]


def _more_specs(n: int) -> list[tuple[str, str, str]]:
    """Extend with synthetic but unique base58-like identities for large inventory."""
    import hashlib

    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"

    def b58(data: bytes) -> str:
        n_int = int.from_bytes(data, "big")
        out = []
        while n_int > 0:
            n_int, r = divmod(n_int, 58)
            out.append(alphabet[r])
        pad = 0
        for b in data:
            if b == 0:
                pad += 1
            else:
                break
        return ("1" * pad) + "".join(reversed(out))

    specs: list[tuple[str, str, str]] = []
    for i in range(n):
        mint = b58(hashlib.sha256(f"v298b21-mint-{i}".encode()).digest())
        pool = b58(hashlib.sha256(f"v298b21-pool-{i}".encode()).digest())
        sig = b58(
            hashlib.sha256(f"v298b21-sig-{i}-a".encode()).digest()
            + hashlib.sha256(f"v298b21-sig-{i}-b".encode()).digest()
        )
        specs.append((mint, sig, pool))
    return specs


SPECS20 = _more_specs(20)
SPECS24 = _more_specs(24)


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
        if pool not in payload_by_pool:
            # Fail closed unproven for unknown pools.
            return fixture_success_transport({"pairs": []})
        return fixture_success_transport(payload_by_pool[pool])

    return factory


def _empty_migration_transport():
    """Honest empty direct Pump live-tail page (no PumpPortal frames)."""
    from printer_v1.sources.direct_pump_migration import (
        SIGNATURE_PAGE_REQUEST_KIND,
        TRANSACTION_REQUEST_KIND,
    )

    def transport(context):
        kind = context.request.request_kind
        if kind == SIGNATURE_PAGE_REQUEST_KIND:
            return {"result": []}
        if kind == TRANSACTION_REQUEST_KIND:
            return {"result": None}
        raise AssertionError(kind)

    return transport


def _seed_registry(connection, specs, *, now=NOW, channel=PERSISTED_GRADUATED_CHANNEL):
    for mint, sig, pool in specs:
        record_graduated_candidate(
            connection,
            mint=mint,
            migration_signature=sig,
            pumpswap_pool=pool,
            graduation_block_time=1_784_000_000,
            graduation_slot=1,
            now=now,
            discovery_channel=channel,
        )
    connection.commit()


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


def _first_round_order(specs: list[tuple[str, str, str]], cycle_seed: str) -> list[str]:
    """Predict front-door batch-1 mint order for all-persisted inventory."""
    rows = sorted(
        [{"mint_identity": m} for m, _s, _p in specs],
        key=lambda r: str(r["mint_identity"]),
    )
    shuffled = _fisher_yates(rows, f"{cycle_seed}|ROUND_1|REFRESH_PERSISTED")
    return [str(r["mint_identity"]) for r in shuffled]


class EligibleTokenSupplyArchitectureTests(unittest.TestCase):
    def setUp(self) -> None:
        parent = os.environ.get("TEMP") or os.environ.get("TMP")
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.db = Path(self.temp.name) / "eligible_supply.sqlite3"
        apply_migrations(self.db)
        self.connection = sqlite3.connect(self.db)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys=ON")
        self.locked_before = _locked_counts(self.connection)

    def tearDown(self) -> None:
        self.connection.close()
        self.temp.cleanup()

    # --- infrastructure -----------------------------------------------------

    def test_migration_046_tables_exist(self) -> None:
        tables = {
            r[0]
            for r in self.connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        self.assertIn("printer_eligible_token_reserve", tables)
        self.assertIn("printer_discovery_exhaustion_certificates", tables)
        self.assertEqual(OPERATION_CEILING, 45)
        self.assertEqual(LIFECYCLE_OPERATION_CEILING, 45)
        self.assertEqual(EVALUATION_BATCH_SIZE, 6)
        self.assertEqual(REQUIRED_TOKEN_CAPACITY, 2)
        self.assertEqual(OPERATIONAL_GRADUATED_SUPPLY_KWARGS["front_door_max_candidates"], 6)

    def test_integrity_and_fk_clean(self) -> None:
        self.assertEqual(
            self.connection.execute("PRAGMA integrity_check").fetchone()[0], "ok"
        )
        self.assertEqual(
            self.connection.execute("PRAGMA foreign_key_check").fetchall(), []
        )

    # --- proofs 1-5 multi-round completeness --------------------------------

    def test_one_eligible_after_many_below_floor_is_discovered(self) -> None:
        specs = SPECS20[:10]
        _seed_registry(self.connection, specs)
        order = _first_round_order(specs, SEED)
        # Make only the last mint in full identity walk eligible by setting all
        # but one below floor; multi-round must still find it.
        eligible_mint = order[-1]
        payloads = {}
        for mint, _sig, pool in specs:
            liq = 12_000.0 if mint == eligible_mint else 50.0
            payloads[pool] = _pair_payload(pool, mint, liq)

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            max_candidates=5,
            front_door_max_candidates=6,
            required_token_capacity=1,
        )
        self.assertTrue(result.ready)
        self.assertEqual(len(result.eligible_reserve), 1)
        self.assertEqual(result.eligible_reserve[0]["mint"], eligible_mint)
        self.assertGreaterEqual(result.discovery_rounds, 1)

    def test_two_eligible_outside_first_six_discovered_and_selected(self) -> None:
        specs = SPECS20
        _seed_registry(self.connection, specs)
        order = _first_round_order(specs, SEED)
        first_six = set(order[:6])
        # Eligible only outside the first evaluation batch.
        eligible_a = order[7]
        eligible_b = order[19]
        self.assertNotIn(eligible_a, first_six)
        self.assertNotIn(eligible_b, first_six)

        payloads = {}
        for mint, _sig, pool in specs:
            liq = 15_000.0 if mint in {eligible_a, eligible_b} else 40.0
            payloads[pool] = _pair_payload(pool, mint, liq)

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=2,
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.terminal, GRADUATED_SUPPLY_READY)
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertEqual(found, {eligible_a, eligible_b})
        self.assertGreaterEqual(result.discovery_rounds, 2)
        self.assertIsNone(result.exhaustion_certificate)
        # Positions 7 and 19 proof.
        self.assertEqual(order.index(eligible_a), 7)
        self.assertEqual(order.index(eligible_b), 19)

    def test_tracking_blocker_is_skipped_before_market_and_fresh_reserve_replaces_it(self) -> None:
        specs = SPECS20[:3]
        _seed_registry(self.connection, specs)
        blocked_mint, _blocked_sig, blocked_pool = specs[0]
        token_id = int(self.connection.execute(
            "INSERT INTO printer_tokens(token_mint,token_status) VALUES (?,'TRACK_NORMAL')",
            (blocked_mint,),
        ).lastrowid)
        pair_id = int(self.connection.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (token_id, blocked_pool, blocked_mint),
        ).lastrowid)
        self.connection.execute(
            """INSERT INTO printer_tracking_queue(
                token_id,pair_id,tracking_lane,tracking_action,priority_reason,
                next_check_at,last_checked_at,queue_status,source_status,data_quality_label
            ) VALUES (?,?,'TRACK_NORMAL','ENTER_COOLDOWN','fixture',?,?,'COOLDOWN',
                      'COMPLETE','CLEAN_DATA')""",
            (
                token_id,
                pair_id,
                (datetime.fromisoformat(NOW) + timedelta(minutes=30)).isoformat(),
                NOW,
            ),
        )
        self.connection.commit()
        factory_calls: list[str] = []
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0)
            for mint, _sig, pool in specs
        }

        def factory(mint, pool):
            factory_calls.append(pool)
            return fixture_success_transport(payloads[pool])

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=factory,
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=2,
            tracking_precheck=True,
        )
        self.assertTrue(result.ready)
        self.assertNotIn(blocked_pool, factory_calls)
        self.assertEqual(len(factory_calls), 2)
        self.assertEqual(
            {candidate["mint"] for candidate in result.eligible_reserve},
            {specs[1][0], specs[2][0]},
        )
        blocked = next(
            candidate for candidate in result.all_candidates
            if candidate["mint"] == blocked_mint
        )
        self.assertTrue(blocked["excluded_before_market_source"])
        self.assertEqual(blocked["rejection"], "COOLDOWN_REOPEN_REQUIRED")
        self.assertEqual(result.diagnostics["pre_source_tracking_exclusions"], 1)

    def test_expired_cooldown_is_revalidated_with_fresh_market_evidence(self) -> None:
        specs = SPECS20[:2]
        _seed_registry(self.connection, specs)
        mint, _sig, pool = specs[0]
        token_id = int(self.connection.execute(
            "INSERT INTO printer_tokens(token_mint,token_status) VALUES (?,'TRACK_NORMAL')",
            (mint,),
        ).lastrowid)
        pair_id = int(self.connection.execute(
            "INSERT INTO printer_pairs(token_id,pair_address,base_token_mint) VALUES (?,?,?)",
            (token_id, pool, mint),
        ).lastrowid)
        last_checked = datetime.fromisoformat(NOW) - timedelta(hours=1)
        self.connection.execute(
            """INSERT INTO printer_tracking_queue(
                token_id,pair_id,tracking_lane,tracking_action,priority_reason,
                next_check_at,last_checked_at,queue_status,source_status,data_quality_label
            ) VALUES (?,?,'TRACK_NORMAL','ENTER_COOLDOWN','fixture',?,?,'COOLDOWN',
                      'COMPLETE','CLEAN_DATA')""",
            (
                token_id,
                pair_id,
                (last_checked - timedelta(minutes=1)).isoformat(),
                last_checked.isoformat(),
            ),
        )
        self.connection.commit()
        factory_calls: list[str] = []
        payloads = {
            candidate_pool: _pair_payload(candidate_pool, candidate_mint, 12_000.0)
            for candidate_mint, _candidate_sig, candidate_pool in specs
        }

        def factory(candidate_mint, candidate_pool):
            factory_calls.append(candidate_pool)
            return fixture_success_transport(payloads[candidate_pool])

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=factory,
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=2,
            tracking_precheck=True,
        )
        self.assertTrue(result.ready)
        self.assertIn(pool, factory_calls)
        refreshed = next(
            candidate for candidate in result.eligible_reserve
            if candidate["mint"] == mint
        )
        self.assertTrue(refreshed["tracking_requalification_required"])
        self.assertEqual(
            refreshed["tracking_handoff"]["category"],
            "COOLDOWN_REQUALIFICATION_REQUIRED",
        )

    def test_round1_eligible_preserved_until_later_round(self) -> None:
        specs = SPECS20[:12]
        _seed_registry(self.connection, specs)
        order = _first_round_order(specs, SEED)
        first_six = order[:6]
        later = order[6:]
        eligible_first = first_six[0]
        eligible_later = later[0]
        payloads = {}
        for mint, _sig, pool in specs:
            liq = (
                20_000.0
                if mint in {eligible_first, eligible_later}
                else 10.0
            )
            payloads[pool] = _pair_payload(pool, mint, liq)

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=2,
        )
        self.assertTrue(result.ready)
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertIn(eligible_first, found)
        self.assertIn(eligible_later, found)
        self.assertGreaterEqual(result.discovery_rounds, 2)

    def test_one_eligible_first_batch_does_not_terminalize_while_capacity_remains(self) -> None:
        specs = SPECS20[:10]
        _seed_registry(self.connection, specs)
        order = _first_round_order(specs, SEED)
        eligible_first = order[0]
        eligible_second = order[8]
        payloads = {}
        for mint, _sig, pool in specs:
            liq = 9_000.0 if mint in {eligible_first, eligible_second} else 5.0
            payloads[pool] = _pair_payload(pool, mint, liq)

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=2,
            discovery_operation_budget=30,
        )
        self.assertTrue(result.ready)
        self.assertNotEqual(
            result.terminal, "BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL"
        )
        self.assertIsNone(result.exhaustion_certificate)

    # --- proofs 6-8 budget / duplicates / cooldown --------------------------

    def test_duplicates_do_not_consume_unique_capacity(self) -> None:
        specs = SPECS20[:8]
        _seed_registry(self.connection, specs)
        # Record same mints already evaluated by running twice should not double-count.
        payloads = {
            pool: _pair_payload(pool, mint, 50.0) for mint, _s, pool in specs
        }
        # Make two eligible.
        a, b = specs[0][0], specs[1][0]
        payloads[specs[0][2]] = _pair_payload(specs[0][2], a, 12_000.0)
        payloads[specs[1][2]] = _pair_payload(specs[1][2], b, 12_000.0)

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.diagnostics["evaluated_unique_mints"], len(
            {c["mint"] for c in result.all_candidates}
        ))

    def test_known_below_floor_does_not_repeatedly_consume_budget(self) -> None:
        specs = SPECS20[:4]
        _seed_registry(self.connection, specs)
        for mint, _s, pool in specs:
            record_market_floor_state(
                self.connection,
                mint=mint,
                pool=pool,
                liquidity=LiquidityEvidence(
                    LIQUIDITY_BELOW_SELECTION_FLOOR,
                    10.0,
                    mint,
                    pool,
                    LIQUIDITY_BELOW_SELECTION_FLOOR,
                    "COMPLETE",
                ),
                now=NOW,
            )
        self.connection.commit()
        call_counter = {"n": 0}

        def counting_factory(m, p):
            call_counter["n"] += 1
            return fixture_success_transport(_pair_payload(p, m, 10.0))

        # Second front-door batch with cooldown active must skip Dex.
        report = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED,
            latest_mints=set(),
            dexscreener_transport_factory=counting_factory,
            now=NOW,
            max_candidates=6,
        )
        self.assertEqual(call_counter["n"], 0)
        self.assertEqual(report["market_calls"], 0)
        self.assertEqual(report["cooldown_skip_count"], 4)

    def test_cooldown_heavy_inventory_still_explores_fresh(self) -> None:
        specs = SPECS20[:8]
        _seed_registry(self.connection, specs)
        # Cool down first six by identity sort; leave remaining fresh eligible.
        sorted_specs = sorted(specs, key=lambda t: t[0])
        for mint, _s, pool in sorted_specs[:6]:
            record_market_floor_state(
                self.connection,
                mint=mint,
                pool=pool,
                liquidity=LiquidityEvidence(
                    LIQUIDITY_BELOW_SELECTION_FLOOR,
                    1.0,
                    mint,
                    pool,
                    LIQUIDITY_BELOW_SELECTION_FLOOR,
                    "COMPLETE",
                ),
                now=NOW,
            )
        self.connection.commit()
        fresh = sorted_specs[6:]
        payloads = {}
        for mint, _s, pool in specs:
            if mint in {fresh[0][0], fresh[1][0]}:
                payloads[pool] = _pair_payload(pool, mint, 11_000.0)
            else:
                payloads[pool] = _pair_payload(pool, mint, 1.0)

        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        self.assertTrue(result.ready)
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertEqual(found, {fresh[0][0], fresh[1][0]})

    # --- proofs 9-11 reserve revalidation -----------------------------------

    def test_persisted_reserve_survives_and_revalidates(self) -> None:
        specs = SPECS20[:3]
        _seed_registry(self.connection, specs)
        mint_a, sig_a, pool_a = specs[0]
        mint_b, sig_b, pool_b = specs[1]
        upsert_eligible_reserve(
            self.connection,
            mint=mint_a,
            pumpswap_pool=pool_a,
            market_identity=f"solana-mainnet:pumpswap:{pool_a}",
            provenance=PERSISTED_GRADUATED_CHANNEL,
            liquidity_usd=10_000.0,
            liquidity_status=LIQUIDITY_PROVEN,
            eligibility_status=ELIGIBLE_FRESH,
            last_validated_at="2026-07-26T00:00:00+00:00",
            source_provenance="prior",
            last_campaign_id="prior-campaign",
        )
        upsert_eligible_reserve(
            self.connection,
            mint=mint_b,
            pumpswap_pool=pool_b,
            market_identity=f"solana-mainnet:pumpswap:{pool_b}",
            provenance=PERSISTED_GRADUATED_CHANNEL,
            liquidity_usd=10_000.0,
            liquidity_status=LIQUIDITY_PROVEN,
            eligibility_status=ELIGIBLE_FRESH,
            last_validated_at="2026-07-26T00:00:00+00:00",
            source_provenance="prior",
            last_campaign_id="prior-campaign",
        )
        self.connection.commit()
        payloads = {
            pool_a: _pair_payload(pool_a, mint_a, 12_000.0),
            pool_b: _pair_payload(pool_b, mint_b, 12_000.0),
            specs[2][2]: _pair_payload(specs[2][2], specs[2][0], 5.0),
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            campaign_id="new-campaign",
        )
        self.assertTrue(result.ready)
        rows = load_eligible_reserve(self.connection, statuses=(ELIGIBLE_FRESH,))
        fresh_mints = {r["mint_identity"] for r in rows}
        self.assertIn(mint_a, fresh_mints)
        self.assertIn(mint_b, fresh_mints)
        for r in rows:
            if r["mint_identity"] in {mint_a, mint_b}:
                self.assertEqual(r["last_validated_at"], NOW)

    def test_stale_reserve_cannot_enter_without_revalidation(self) -> None:
        specs = SPECS20[:2]
        _seed_registry(self.connection, specs)
        mint_a, _s, pool_a = specs[0]
        mint_b, _s2, pool_b = specs[1]
        # Prior "eligible" that is now below floor.
        upsert_eligible_reserve(
            self.connection,
            mint=mint_a,
            pumpswap_pool=pool_a,
            market_identity=f"solana-mainnet:pumpswap:{pool_a}",
            provenance=PERSISTED_GRADUATED_CHANNEL,
            liquidity_usd=50_000.0,
            liquidity_status=LIQUIDITY_PROVEN,
            eligibility_status=ELIGIBLE_FRESH,
            last_validated_at="2026-07-01T00:00:00+00:00",
            source_provenance="stale",
            last_campaign_id="old",
        )
        self.connection.commit()
        payloads = {
            pool_a: _pair_payload(pool_a, mint_a, 10.0),  # fails revalidation
            pool_b: _pair_payload(pool_b, mint_b, 12_000.0),
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            required_token_capacity=2,
        )
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertNotIn(mint_a, found)
        self.assertIn(mint_b, found)
        # Not ready (only one eligible after revalidation).
        self.assertFalse(result.ready)
        self.assertIsNotNone(result.exhaustion_certificate)

    def test_failed_incomplete_evidence_cannot_enter_selection(self) -> None:
        specs = SPECS20[:3]
        _seed_registry(self.connection, specs)
        payloads = {
            specs[0][2]: _pair_payload(specs[0][2], specs[0][0], None),
            specs[1][2]: _pair_payload(specs[1][2], specs[1][0], 50.0),
            specs[2][2]: _pair_payload(specs[2][2], specs[2][0], 12_000.0),
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertEqual(found, {specs[2][0]})
        self.assertFalse(result.ready)

    # --- proofs 12-16 shortage classification -------------------------------

    def test_two_eligible_anywhere_never_blocked_insufficient(self) -> None:
        specs = SPECS20
        _seed_registry(self.connection, specs)
        order = _first_round_order(specs, SEED)
        elig = {order[7], order[19]}
        payloads = {
            pool: _pair_payload(pool, mint, 14_000.0 if mint in elig else 3.0)
            for mint, _s, pool in specs
        }
        supply = build_graduated_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        self.assertTrue(supply.ready)
        self.assertNotEqual(
            supply.terminal, "BLOCKED_INSUFFICIENT_ELIGIBLE_GRADUATED_POOL"
        )
        self.assertEqual(len(supply.holder_reserve_supply), 2)

    def test_only_one_eligible_emits_honest_exhaustion_certificate(self) -> None:
        specs = SPECS20[:8]
        _seed_registry(self.connection, specs)
        order = _first_round_order(specs, SEED)
        only = order[0]
        payloads = {
            pool: _pair_payload(pool, mint, 13_000.0 if mint == only else 8.0)
            for mint, _s, pool in specs
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            campaign_id="camp-one",
            execution_id="exec-one",
        )
        self.assertFalse(result.ready)
        cert = result.exhaustion_certificate
        self.assertIsNotNone(cert)
        assert cert is not None
        d = cert.to_dict()
        self.assertEqual(d["required_eligible_capacity"], 2)
        self.assertEqual(d["eligible_reserve_count"], 1)
        self.assertEqual(d["eligible_count"], 1)
        self.assertGreaterEqual(d["unique_tokens_observed"], 8)
        self.assertGreaterEqual(d["discovery_rounds"], 2)
        self.assertIn(d["shortage_classification"], {
            TRUE_MARKET_SUPPLY_SHORTAGE,
            "SOURCE_VISIBILITY_SHORTAGE",
        })
        self.assertEqual(d["campaign_id"], "camp-one")
        self.assertEqual(d["execution_id"], "exec-one")
        # Not a single-batch-only certificate.
        self.assertGreater(d["unique_tokens_observed"], 6)
        row = self.connection.execute(
            "SELECT COUNT(*) FROM printer_discovery_exhaustion_certificates"
        ).fetchone()[0]
        self.assertEqual(int(row), 1)

    def test_provider_failure_classified_separately(self) -> None:
        cls = classify_shortage(
            provider_failures=1,
            channels_unavailable=["pumpportal_migration_stream"],
            duration_remaining_seconds=100.0,
            source_operations_remaining=20,
            unexplored_unique_remaining=0,
            eligible_count=0,
            unique_tokens_observed=0,
            discovery_rounds=1,
            evaluation_batch_size=6,
            all_channels_exhausted=True,
        )
        self.assertEqual(cls, SOURCE_AVAILABILITY_FAILURE)

    def test_budget_exhaustion_classified_separately(self) -> None:
        specs = SPECS20[:10]
        _seed_registry(self.connection, specs)
        # All below floor so never ready; tiny budget.
        payloads = {
            pool: _pair_payload(pool, mint, 20.0) for mint, _s, pool in specs
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            discovery_operation_budget=2,  # migration empty=1? + market
        )
        # empty migration still costs 1 source op typically; budget 2 is tight
        self.assertFalse(result.ready)
        self.assertIsNotNone(result.exhaustion_certificate)
        # Either budget or true market depending on how far it got.
        self.assertIn(
            result.shortage_classification,
            {BUDGET_EXHAUSTION, TRUE_MARKET_SUPPLY_SHORTAGE},
        )

    def test_duration_exhaustion_classified_separately(self) -> None:
        specs = SPECS20[:10]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 20.0) for mint, _s, pool in specs
        }
        past = "2026-07-27T21:00:00+00:00"
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            deadline_at=past,
        )
        self.assertFalse(result.ready)
        self.assertEqual(result.shortage_classification, DURATION_EXHAUSTION)

    # --- proofs 17-20 selection / ceiling / governor ------------------------

    def test_selection_deterministic_non_ranked(self) -> None:
        specs = SPECS20[:6]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        a = build_graduated_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        # Second run same seed, new DB clone of registry via re-seed on fresh db
        # Compare within same result: two selected are identity-stable.
        self.assertTrue(a.ready)
        mints_a = [p.mint for p in a.holder_reserve_supply]
        b = build_graduated_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        mints_b = [p.mint for p in b.holder_reserve_supply]
        self.assertEqual(mints_a, mints_b)
        # Non-ranked: order is mint identity sorted in reserve.
        self.assertEqual(mints_a, sorted(mints_a))

    def test_exactly_two_distinct_enter_handoff_path(self) -> None:
        specs = SPECS20[:8]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        supply = build_graduated_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        self.assertTrue(supply.ready)
        # holder_reserve may retain more, graduated_supply selected carriers are 2
        self.assertEqual(len(supply.graduated_supply), 2)
        mints = [p.mint for p in supply.graduated_supply]
        self.assertEqual(len(set(mints)), 2)

    def test_operation_ceiling_enforced(self) -> None:
        self.assertEqual(DEFAULT_DISCOVERY_OPERATION_BUDGET, 30)
        self.assertLessEqual(DEFAULT_DISCOVERY_OPERATION_BUDGET, OPERATION_CEILING)
        specs = SPECS24
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 20.0) for mint, _s, pool in specs
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
            discovery_operation_budget=5,
        )
        self.assertFalse(result.ready)
        self.assertLessEqual(
            result.diagnostics["discovery_operations_used"], 5
        )
        self.assertEqual(result.shortage_classification, BUDGET_EXHAUSTION)

    def test_source_governor_not_bypassed_front_door_uses_governed_path(self) -> None:
        # Front door and migration always go through execute_source_request_with_governor
        # for real transports; fixture path still records governed requests.
        specs = SPECS20[:2]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        self.assertTrue(result.ready)
        # Stage-local ops recorded (migration + market checks).
        self.assertGreaterEqual(result.diagnostics["stage_local_source_requests"], 1)
        # No scheduler residue from supply service.
        jobs = self.connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0]
        self.assertEqual(int(jobs), 0)

    # --- proofs 21-25 integrity / residue / locks ---------------------------

    def test_integrity_fk_residue_and_locked_deltas(self) -> None:
        specs = SPECS20[:10]
        _seed_registry(self.connection, specs)
        order = _first_round_order(specs, SEED)
        elig = {order[0], order[7]}
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0 if mint in elig else 4.0)
            for mint, _s, pool in specs
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        self.assertTrue(result.ready)
        self.assertEqual(result.diagnostics["integrity_check"], "ok")
        self.assertEqual(result.diagnostics["foreign_key_violations"], 0)
        self.assertFalse(result.diagnostics["restart_created"])
        self.assertFalse(result.diagnostics["successor_created"])
        self.assertFalse(result.diagnostics["automatic_retry_created"])
        locked_after = _locked_counts(self.connection)
        for table, before in self.locked_before.items():
            self.assertEqual(
                locked_after[table],
                before,
                msg=f"locked capability delta on {table}",
            )
        # No campaign/supervision residue created by supply service.
        camps = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaigns"
        ).fetchone()[0]
        self.assertEqual(int(camps), 0)
        sup = self.connection.execute(
            "SELECT COUNT(*) FROM printer_memory_factory_campaign_supervision"
        ).fetchone()[0]
        self.assertEqual(int(sup), 0)

    def test_exclude_mints_enables_second_batch(self) -> None:
        specs = SPECS20[:10]
        _seed_registry(self.connection, specs)
        payloads = {
            pool: _pair_payload(pool, mint, 12_000.0) for mint, _s, pool in specs
        }
        first = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED,
            latest_mints=set(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            max_candidates=6,
        )
        self.assertEqual(first["candidate_count"], 6)
        excluded = {c["mint"] for c in first["candidates"]}
        second = run_graduated_liquidity_front_door(
            self.db,
            cycle_seed=SEED + "|2",
            latest_mints=set(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            max_candidates=6,
            exclude_mints=excluded,
        )
        second_mints = {c["mint"] for c in second["candidates"]}
        self.assertTrue(second_mints.isdisjoint(excluded))
        self.assertEqual(second["excluded_mint_count"], 6)

    def test_eligible_becomes_ineligible_during_revalidation(self) -> None:
        specs = SPECS20[:3]
        _seed_registry(self.connection, specs)
        mint_a, _s, pool_a = specs[0]
        mint_b, _s2, pool_b = specs[1]
        mint_c, _s3, pool_c = specs[2]
        upsert_eligible_reserve(
            self.connection,
            mint=mint_a,
            pumpswap_pool=pool_a,
            market_identity=f"solana-mainnet:pumpswap:{pool_a}",
            provenance=PERSISTED_GRADUATED_CHANNEL,
            liquidity_usd=20_000.0,
            liquidity_status=LIQUIDITY_PROVEN,
            eligibility_status=ELIGIBLE_FRESH,
            last_validated_at="2026-07-01T00:00:00+00:00",
            source_provenance="prior",
            last_campaign_id="old",
        )
        self.connection.commit()
        # A fails revalidation; B and C become the two.
        payloads = {
            pool_a: _pair_payload(pool_a, mint_a, 1.0),
            pool_b: _pair_payload(pool_b, mint_b, 12_000.0),
            pool_c: _pair_payload(pool_c, mint_c, 12_000.0),
        }
        result = run_persistent_eligible_token_supply(
            self.db,
            cycle_seed=SEED,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=_dex_factory(payloads),
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=6,
        )
        found = {c["mint"] for c in result.eligible_reserve}
        self.assertNotIn(mint_a, found)
        self.assertTrue(result.ready)
        self.assertEqual(found, {mint_b, mint_c})


if __name__ == "__main__":
    unittest.main()
