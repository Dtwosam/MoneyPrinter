"""Focused offline proof for the V2-9.8B liquidity evidence repair.

Fixtures and temporary migrated SQLite databases only. No network, Scheduler,
campaign, lifecycle, memory, retry, restart, or successor runtime is invoked.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from types import SimpleNamespace

import pytest

from printer_v1.db import apply_migrations
from printer_v1.discovery.eligible_token_supply import (
    BUDGET_EXHAUSTION,
    ELIGIBLE_FRESH,
    REMOVED,
    SOURCE_AVAILABILITY_FAILURE,
    SOURCE_VISIBILITY_SHORTAGE,
    STALE_EVIDENCE_SHORTAGE,
    TRUE_MARKET_SUPPLY_SHORTAGE,
    run_persistent_eligible_token_supply,
    upsert_eligible_reserve,
)
from printer_v1.discovery.graduated_liquidity_front_door import (
    LIQUIDITY_EXACT_ABOVE_FLOOR,
    LIQUIDITY_EXACT_BELOW_FLOOR,
    LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH,
    LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL,
    LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE,
    LIQUIDITY_SOURCE_UNAVAILABLE,
    enrich_pool_liquidity,
    run_graduated_liquidity_front_door,
)
from printer_v1.operator_cli.authoritative_live_operational_campaign import (
    BLOCKED_INSUFFICIENT_GRADUATED_POOL,
    _graduated_supply_terminal_cause,
)
from printer_v1.operator_cli.unified_terminal_closure import (
    build_blocked_supply_reporting,
    build_campaign_terminal_report,
)
from printer_v1.sources.dexscreener import (
    fixture_rate_limited_transport,
    fixture_success_transport,
)
from printer_v1.sources.pumpswap_graduated_registry import (
    PERSISTED_GRADUATED_CHANNEL,
    record_graduated_candidate,
)


NOW = "2026-07-28T22:00:00+00:00"
ALPHABET = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def _b58(data: bytes) -> str:
    value = int.from_bytes(data, "big")
    out: list[str] = []
    while value:
        value, remainder = divmod(value, 58)
        out.append(ALPHABET[remainder])
    return "".join(reversed(out)) or "1"


def _spec(index: int) -> tuple[str, str, str]:
    mint = _b58(hashlib.sha256(f"liq-mint-{index}".encode()).digest())
    pool = _b58(hashlib.sha256(f"liq-pool-{index}".encode()).digest())
    signature = _b58(
        hashlib.sha256(f"liq-sig-a-{index}".encode()).digest()
        + hashlib.sha256(f"liq-sig-b-{index}".encode()).digest()
    )
    return mint, signature, pool


def _db(tmp_path) -> str:
    path = tmp_path / "liquidity-repair.sqlite3"
    apply_migrations(path)
    return str(path)


def _seed(db: str, count: int) -> list[tuple[str, str, str]]:
    specs = [_spec(index) for index in range(count)]
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        for index, (mint, signature, pool) in enumerate(specs):
            record_graduated_candidate(
                connection,
                mint=mint,
                migration_signature=signature,
                pumpswap_pool=pool,
                graduation_block_time=1_784_841_493 + index,
                graduation_slot=1 + index,
                now=NOW,
                discovery_channel=PERSISTED_GRADUATED_CHANNEL,
            )
        connection.commit()
    finally:
        connection.close()
    return specs


def _pair(pool: str, mint: str, liquidity: float | None) -> dict:
    return {
        "pairs": [{
            "chainId": "solana",
            "pairAddress": pool,
            "baseToken": {"address": mint, "symbol": "MEME", "name": "Meme"},
            "priceUsd": "0.10",
            "liquidity": {} if liquidity is None else {"usd": liquidity},
            "volume": {"m5": 1.0, "h1": 2.0, "h24": 3.0},
            "txns": {"m5": {"buys": 1, "sells": 1}},
        }]
    }


def _empty_migration_transport():
    def transport(_context):
        return {
            "request_kind": "pumpfun_migration_stream",
            "source_name": "pumpportal",
            "tokens": [],
        }
    return transport


def _success_factory(values: dict[str, tuple[str, float | None]]):
    def factory(_mint, pool):
        mint, liquidity = values[pool]
        return fixture_success_transport(_pair(pool, mint, liquidity))
    return factory


def _transport_failure_factory(_mint, _pool):
    return fixture_success_transport({
        "fixture_status": "failure",
        "failure_type": "dexscreener_transport_failure",
        "failure_message": "<urlopen error [Errno 65] No route to host>",
    })


def _front_door(db: str, factory, count: int) -> dict:
    return run_graduated_liquidity_front_door(
        db,
        cycle_seed="liquidity-repair-seed",
        latest_mints=set(),
        dexscreener_transport_factory=factory,
        now=NOW,
        max_candidates=count,
    )


def test_exact_above_and_below_floor_preserve_response_lineage(tmp_path) -> None:
    db = _db(tmp_path)
    specs = _seed(db, 2)
    values = {
        specs[0][2]: (specs[0][0], 3_000.0),
        specs[1][2]: (specs[1][0], 2_999.99),
    }
    report = _front_door(db, _success_factory(values), 2)
    evidence = {item["mint"]: item["liquidity"] for item in report["candidates"]}

    above = evidence[specs[0][0]]
    below = evidence[specs[1][0]]
    assert above["outcome_category"] == LIQUIDITY_EXACT_ABOVE_FLOOR
    assert below["outcome_category"] == LIQUIDITY_EXACT_BELOW_FLOOR
    for item in (above, below):
        assert item["source_request_id"] is not None
        assert item["source_response_id"] is not None
        assert item["source_failure_id"] is None
        assert item["mint"] and item["pool"]
        assert item["source_status"] == "COMPLETE"


@pytest.mark.parametrize(
    ("transport", "category", "failure_expected"),
    [
        (fixture_rate_limited_transport(), LIQUIDITY_SOURCE_RATE_LIMITED_OR_STALE, True),
        (fixture_success_transport({"bad": "payload"}), LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL, True),
        (fixture_success_transport({"pairs": []}), LIQUIDITY_RESPONSE_MALFORMED_OR_PARTIAL, False),
    ],
)
def test_rate_limit_malformed_and_partial_are_distinct_lineaged_outcomes(
    tmp_path, transport, category, failure_expected
) -> None:
    db = _db(tmp_path)
    mint, _signature, pool = _seed(db, 1)[0]
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        evidence = enrich_pool_liquidity(
            connection,
            mint=mint,
            pumpswap_pool=pool,
            dexscreener_transport=transport,
            request_key=f"repair-{category}",
        ).to_dict()
    finally:
        connection.close()
    assert evidence["outcome_category"] == category
    assert evidence["source_request_id"] is not None
    assert (evidence["source_failure_id"] is not None) is failure_expected
    assert (evidence["source_response_id"] is not None) is (not failure_expected)


def test_no_exact_pair_and_mint_pool_mismatches_are_not_provider_outages(tmp_path) -> None:
    db = _db(tmp_path)
    specs = _seed(db, 3)
    target_mint, _signature, target_pool = specs[0]
    cases = [
        _pair(specs[1][2], specs[1][0], 9_000.0),
        _pair(target_pool, specs[1][0], 9_000.0),
        _pair(specs[1][2], target_mint, 9_000.0),
    ]
    reasons = []
    for index, payload in enumerate(cases):
        connection = sqlite3.connect(db)
        connection.row_factory = sqlite3.Row
        try:
            evidence = enrich_pool_liquidity(
                connection,
                mint=target_mint,
                pumpswap_pool=target_pool,
                dexscreener_transport=fixture_success_transport(payload),
                request_key=f"identity-case-{index}",
            ).to_dict()
        finally:
            connection.close()
        assert evidence["outcome_category"] == LIQUIDITY_EXACT_PAIR_UNAVAILABLE_OR_MISMATCH
        assert evidence["source_response_id"] is not None
        assert evidence["source_failure_id"] is None
        reasons.append(evidence["reason"])
    assert reasons == [
        "LIQUIDITY_NO_EXACT_PAIR",
        "LIQUIDITY_MINT_MISMATCH",
        "LIQUIDITY_POOL_MISMATCH_TOKEN_LEVEL",
    ]


def test_24_identical_transport_failures_are_source_unavailability_with_ownership(
    tmp_path,
) -> None:
    db = _db(tmp_path)
    _seed(db, 24)
    result = run_persistent_eligible_token_supply(
        db,
        cycle_seed="execution-24-failures",
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=_transport_failure_factory,
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=24,
        discovery_operation_budget=30,
        campaign_id="campaign-24",
        execution_id="execution-24",
        run_id="run-24",
        cycle_id="cycle-24",
    )
    assert result.ready is False
    assert result.shortage_classification == SOURCE_AVAILABILITY_FAILURE
    certificate = result.exhaustion_certificate
    assert certificate is not None
    payload = certificate.to_dict()
    assert payload["provider_failures"] == 24
    assert payload["liquidity_stage_provider_failures"] == 24
    assert payload["channels_unavailable"] == ["dexscreener_exact_pool_market"]
    assert payload["campaign_id"] == "campaign-24"
    assert payload["execution_id"] == "execution-24"
    assert payload["run_id"] == "run-24"
    assert payload["cycle_id"] == "cycle-24"
    assert len(payload["candidate_liquidity_lineage"]) == 24
    for item in payload["candidate_liquidity_lineage"]:
        assert item["source_request_id"] is not None
        assert item["source_response_id"] is None
        assert item["source_failure_id"] is not None
        assert item["failure_type"] == "dexscreener_transport_failure"
        assert item["detailed_reason"] == "<urlopen error [Errno 65] No route to host>"
        assert item["outcome_category"] == LIQUIDITY_SOURCE_UNAVAILABLE

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        stored = connection.execute(
            "SELECT * FROM printer_discovery_exhaustion_certificates"
        ).fetchone()
        request_count = connection.execute(
            "SELECT COUNT(*) FROM printer_source_requests "
            "WHERE source_name='dexscreener' AND request_kind='pair_market_snapshot'"
        ).fetchone()[0]
        failure_count = connection.execute(
            "SELECT COUNT(*) FROM printer_source_failures "
            "WHERE failure_type='dexscreener_transport_failure'"
        ).fetchone()[0]
    finally:
        connection.close()
    assert stored is not None
    assert tuple(stored[key] for key in ("campaign_id", "execution_id", "run_id", "cycle_id")) == (
        "campaign-24", "execution-24", "run-24", "cycle-24"
    )
    assert json.loads(stored["certificate_json"])["provider_failures"] == 24
    assert request_count == failure_count == 24


def test_mixed_success_and_failure_preserves_both_and_blocks_as_source_unavailable(
    tmp_path,
) -> None:
    db = _db(tmp_path)
    specs = _seed(db, 2)

    def factory(mint, pool):
        if mint == specs[0][0]:
            return fixture_success_transport(_pair(pool, mint, 8_000.0))
        return _transport_failure_factory(mint, pool)

    result = run_persistent_eligible_token_supply(
        db,
        cycle_seed="mixed",
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=factory,
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=2,
        campaign_id="mixed-campaign",
        execution_id="mixed-execution",
        run_id="mixed-run",
        cycle_id="mixed-cycle",
    )
    categories = {
        candidate["liquidity"]["outcome_category"]
        for candidate in result.all_candidates
    }
    assert categories == {LIQUIDITY_EXACT_ABOVE_FLOOR, LIQUIDITY_SOURCE_UNAVAILABLE}
    assert result.shortage_classification == SOURCE_AVAILABILITY_FAILURE
    assert len(result.eligible_reserve) == 1


def test_rate_limit_supply_uses_stale_shortage_and_malformed_uses_visibility(tmp_path) -> None:
    for name, factory, expected in (
        (
            "rate",
            lambda _mint, _pool: fixture_rate_limited_transport(),
            STALE_EVIDENCE_SHORTAGE,
        ),
        (
            "malformed",
            lambda _mint, _pool: fixture_success_transport({"bad": "payload"}),
            SOURCE_VISIBILITY_SHORTAGE,
        ),
    ):
        db = str(tmp_path / f"{name}.sqlite3")
        apply_migrations(db)
        _seed(db, 1)
        result = run_persistent_eligible_token_supply(
            db,
            cycle_seed=name,
            migration_transport=_empty_migration_transport(),
            dexscreener_transport_factory=factory,
            now=NOW,
            collection_rounds=1,
            front_door_max_candidates=1,
        )
        assert result.shortage_classification == expected


def test_budget_exhaustion_and_true_supply_exhaustion_remain_distinct(tmp_path) -> None:
    budget_db = str(tmp_path / "budget.sqlite3")
    apply_migrations(budget_db)
    budget_specs = _seed(budget_db, 4)
    budget_values = {
        pool: (mint, 10.0) for mint, _signature, pool in budget_specs
    }
    budget = run_persistent_eligible_token_supply(
        budget_db,
        cycle_seed="budget",
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=_success_factory(budget_values),
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=4,
        discovery_operation_budget=2,
    )
    assert budget.shortage_classification == BUDGET_EXHAUSTION

    supply_db = str(tmp_path / "supply.sqlite3")
    apply_migrations(supply_db)
    supply_specs = _seed(supply_db, 2)
    supply_values = {
        pool: (mint, 10.0) for mint, _signature, pool in supply_specs
    }
    supply = run_persistent_eligible_token_supply(
        supply_db,
        cycle_seed="true-supply",
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=_success_factory(supply_values),
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=2,
        discovery_operation_budget=30,
    )
    assert supply.shortage_classification == TRUE_MARKET_SUPPLY_SHORTAGE
    assert _graduated_supply_terminal_cause(
        SimpleNamespace(diagnostics={"shortage_classification": TRUE_MARKET_SUPPLY_SHORTAGE})
    ) == BLOCKED_INSUFFICIENT_GRADUATED_POOL
    assert _graduated_supply_terminal_cause(
        SimpleNamespace(diagnostics={"shortage_classification": SOURCE_AVAILABILITY_FAILURE})
    ) == SOURCE_AVAILABILITY_FAILURE


def test_historical_reserve_is_preserved_but_current_attempt_is_not_admitted(tmp_path) -> None:
    db = _db(tmp_path)
    mint, _signature, pool = _seed(db, 1)[0]
    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys=ON")
    try:
        upsert_eligible_reserve(
            connection,
            mint=mint,
            pumpswap_pool=pool,
            market_identity=f"solana-mainnet:pumpswap:{pool}",
            provenance=PERSISTED_GRADUATED_CHANNEL,
            liquidity_usd=9_999.0,
            liquidity_status="LIQUIDITY_PROVEN",
            eligibility_status=ELIGIBLE_FRESH,
            last_validated_at="2026-07-28T20:00:00+00:00",
            source_provenance="historical-exact-proof",
            last_campaign_id="historical-campaign",
        )
        connection.commit()
    finally:
        connection.close()

    result = run_persistent_eligible_token_supply(
        db,
        cycle_seed="historical-revalidation",
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=_transport_failure_factory,
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=1,
        campaign_id="current-campaign",
        execution_id="current-execution",
        run_id="current-run",
        cycle_id="current-cycle",
    )
    assert result.eligible_reserve == []
    candidate = result.all_candidates[0]
    assert candidate["liquidity"]["liquidity_usd"] is None
    historical = candidate["historical_reserve_evidence"]
    assert historical["liquidity_usd"] == 9_999.0
    assert historical["admitted_as_current"] is False
    assert candidate["current_eligibility_status"] == REMOVED

    connection = sqlite3.connect(db)
    connection.row_factory = sqlite3.Row
    try:
        reserve = connection.execute(
            "SELECT * FROM printer_eligible_token_reserve WHERE mint_identity=?",
            (mint,),
        ).fetchone()
        floor = connection.execute(
            "SELECT * FROM printer_graduated_market_floor_state WHERE mint_identity=?",
            (mint,),
        ).fetchone()
    finally:
        connection.close()
    assert reserve["liquidity_usd"] == 9_999.0
    assert reserve["liquidity_status"] == "LIQUIDITY_PROVEN"
    assert reserve["eligibility_status"] == REMOVED
    assert floor["liquidity_status"] == "LIQUIDITY_UNPROVEN"
    assert floor["liquidity_usd"] is None


def test_blocked_supply_and_terminal_artifact_are_truthful_and_keep_locks(tmp_path) -> None:
    db = _db(tmp_path)
    _seed(db, 1)
    result = run_persistent_eligible_token_supply(
        db,
        cycle_seed="terminal",
        migration_transport=_empty_migration_transport(),
        dexscreener_transport_factory=_transport_failure_factory,
        now=NOW,
        collection_rounds=1,
        front_door_max_candidates=1,
        campaign_id="terminal-campaign",
        execution_id="terminal-execution",
        run_id="terminal-run",
        cycle_id="terminal-cycle",
    )
    certificate = result.exhaustion_certificate
    assert certificate is not None
    surface = build_blocked_supply_reporting(
        required_token_capacity=2,
        candidates=result.front_door_report["candidates"],
        blocked_supply_reason=result.shortage_classification,
        campaign_source_calls=certificate.source_operations_used,
        campaign_scheduler_calls=0,
        shortage_classification=result.shortage_classification,
        exhaustion_certificate=certificate.to_dict(),
    )
    terminal = build_campaign_terminal_report(
        campaign_id="terminal-campaign",
        configuration_id="terminal-configuration",
        run_id="terminal-run",
        cycle_id="terminal-cycle",
        report_id="terminal-report",
        factory_run_id=None,
        execution_id="terminal-execution",
        terminal_status=SOURCE_AVAILABILITY_FAILURE,
        terminal_cause=SOURCE_AVAILABILITY_FAILURE,
        run_status="NOT_STARTED",
        lifecycle_started=False,
        reconciliation={"clean_terminal": True},
        campaign_activity=surface["campaign_activity"],
        blocked_supply=surface["blocked_supply"],
    )
    candidate = terminal["blocked_supply"]["candidates"][0]
    assert terminal["terminal"]["first_terminal_cause"] == SOURCE_AVAILABILITY_FAILURE
    assert terminal["shortage_classification"] == SOURCE_AVAILABILITY_FAILURE
    assert terminal["exhaustion_certificate"]["provider_failures"] == 1
    assert terminal["campaign_scheduler_calls"] == 0
    assert terminal["terminal"]["lifecycle_started"] is False
    assert candidate["liquidity_reason"].startswith("LIQUIDITY_SOURCE_")
    assert candidate["liquidity_source_status"] == "FAILED"
    assert candidate["liquidity_source_lineage"]["source_failure_id"] is not None
    assert terminal["restart_created"] is False
    assert terminal["successor_created"] is False
    assert all(value is False for value in terminal["downstream_unlocks"].values())
    assert result.diagnostics["automatic_retry_created"] is False
    assert result.diagnostics["restart_created"] is False
    assert result.diagnostics["successor_created"] is False

    connection = sqlite3.connect(db)
    try:
        four_hour = connection.execute(
            "SELECT COUNT(*) FROM printer_memory_windows WHERE window_kind='WINDOW_4H'"
        ).fetchone()[0]
        scheduler_rows = connection.execute(
            "SELECT COUNT(*) FROM printer_scheduler_jobs"
        ).fetchone()[0]
        lifecycle_rows = connection.execute(
            "SELECT COUNT(*) FROM printer_tracking_queue"
        ).fetchone()[0]
    finally:
        connection.close()
    assert four_hour == scheduler_rows == lifecycle_rows == 0
