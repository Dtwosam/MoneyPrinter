import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest


FIXTURE = Path(__file__).parent / "fixtures" / "secondary_discovery_contracts.json"
IDENTITY_KEYS = {
    "provider", "channel", "network", "mint", "pool", "quote_mint",
    "venue", "observed_at",
}


def _epoch(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def _relationship_mint(resource: dict, name: str) -> str:
    value = resource["relationships"][name]["data"]["id"]
    prefix = "solana_"
    if not value.startswith(prefix) or len(value) == len(prefix):
        raise ValueError("wrong_or_missing_solana_relationship")
    return value[len(prefix):]


def _gecko_identity(resource: dict, channel: str, observed_at: str) -> dict:
    pool = resource["attributes"]["address"]
    if resource.get("type") != "pool" or resource.get("id") != f"solana_{pool}":
        raise ValueError("wrong_pool_identity")
    return {
        "provider": "geckoterminal",
        "channel": channel,
        "network": "solana",
        "mint": _relationship_mint(resource, "base_token"),
        "pool": pool,
        "quote_mint": _relationship_mint(resource, "quote_token"),
        "venue": resource["relationships"]["dex"]["data"]["id"],
        "observed_at": observed_at,
    }


def normalize_gecko_trending(contract: dict, evaluated_at: str) -> list[dict]:
    case = contract["trending"]
    if case["params"] != {
        "include": "base_token,quote_token,dex", "page": 1, "duration": "1h"
    }:
        raise ValueError("unadopted_trending_request")
    if _epoch(evaluated_at) - _epoch(case["receipt_time"]) > contract["stale_after_seconds"]:
        raise ValueError("stale_receipt")
    data = case["body"].get("data")
    if not isinstance(data, list) or len(data) > 20:
        raise ValueError("malformed_or_limit_drift")
    rows = [_gecko_identity(item, "TRENDING_PUMPFUN", case["receipt_time"]) for item in data]
    return sorted(rows, key=lambda row: (row["mint"], row["pool"]))


def normalize_gecko_active(contract: dict, evaluated_at: str) -> dict:
    case = contract["active"]
    if _epoch(evaluated_at) - _epoch(case["receipt_time"]) > contract["stale_after_seconds"]:
        raise ValueError("stale_receipt")
    resource = case["body"]["data"]
    row = _gecko_identity(resource, "ACTIVE_PUMPFUN", case["receipt_time"])
    if row["pool"] != case["requested_pool"]:
        raise ValueError("requested_pool_mismatch")
    activity = resource["attributes"]["transactions"]["m5"]
    buys, sells = activity["buys"], activity["sells"]
    if type(buys) is not int or type(sells) is not int or min(buys, sells) < 0:
        raise ValueError("malformed_activity")
    if buys + sells <= 0:
        raise ValueError("not_active")
    row["activity_interval"] = "m5"
    row["activity_count"] = buys + sells
    return row


def normalize_tracker(case: dict, contract: dict, channel: str, evaluated_at: str) -> list[dict]:
    if _epoch(evaluated_at) - _epoch(case["receipt_time"]) > contract["stale_after_seconds"]:
        raise ValueError("stale_receipt")
    body = case["body"]
    if not isinstance(body, list) or len(body) > 100:
        raise ValueError("malformed_or_limit_drift")
    rows = {}
    for item in body:
        token = item.get("token")
        pools = item.get("pools")
        if not isinstance(token, dict) or not isinstance(pools, list):
            raise ValueError("malformed_token_info")
        mint = token.get("mint")
        if not isinstance(mint, str) or not mint:
            raise ValueError("missing_mint")
        for pool in pools:
            if pool.get("market") != "pumpfun" or pool.get("tokenAddress") != mint:
                continue
            required = ("poolId", "quoteToken", "lastUpdated")
            if any(pool.get(key) in (None, "") for key in required):
                raise ValueError("missing_pool_identity")
            updated = pool["lastUpdated"]
            if type(updated) is not int:
                raise ValueError("malformed_last_updated")
            # Row-level freshness (V2-9.7D.7B.4B.1): stale/future rows contribute
            # nothing; they do not abort the rest of the response body.
            age = _epoch(evaluated_at) - updated / 1000
            if age < -5 or age > contract["stale_after_seconds"]:
                continue
            row = {
                "provider": "solana_tracker",
                "channel": channel,
                "network": "solana",
                "mint": mint,
                "pool": pool["poolId"],
                "quote_mint": pool["quoteToken"],
                "venue": "pumpfun",
                "observed_at": case["receipt_time"],
            }
            identity = (mint, pool["poolId"], channel)
            if identity in rows and rows[identity] != row:
                raise ValueError("conflicting_duplicate")
            rows[identity] = row
    return sorted(rows.values(), key=lambda row: (row["mint"], row["pool"]))


def _load() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_schema_auth_quota_and_blocked_access_contracts():
    fixture = _load()
    gecko = fixture["geckoterminal"]
    tracker = fixture["solana_tracker"]
    assert gecko["base_url"] == "https://api.geckoterminal.com/api/v2"
    assert gecko["authentication"] == "none"
    assert gecko["rate_ceiling_per_minute"] == 10
    assert gecko["cycle_request_ceiling"] == 2
    assert tracker["base_url"] == "https://data.solanatracker.io"
    assert tracker["authentication"] == "x-api-key"
    assert tracker["free_requests_per_month"] == 10_000
    assert tracker["free_requests_per_second"] == 3
    assert tracker["cycle_request_ceiling"] == 2
    assert tracker["trending"]["path"] == "/tokens/trending/1h"
    assert tracker["top"]["path"] == "/top-performers/1h"
    blocked = fixture["blocked_pumpportal"]
    assert blocked["status"] == "SKIPPED_BLOCKED_CONTRACT"
    assert set(blocked["blocked_requirements"]) == {
        "api_key", "linked_wallet", "minimum_0.02_SOL_funding"
    }
    assert "REDACTED" in blocked["websocket"]


def test_adopted_gecko_fields_and_active_condition():
    fixture = _load()
    evaluated = fixture["evaluated_at"]
    rows = normalize_gecko_trending(fixture["geckoterminal"], evaluated)
    assert [row["mint"] for row in rows] == [
        "MintA1111111111111111111111111111111111111",
        "MintB1111111111111111111111111111111111111",
    ]
    assert all(set(row) == IDENTITY_KEYS for row in rows)
    active = normalize_gecko_active(fixture["geckoterminal"], evaluated)
    assert active["mint"] == "MintA1111111111111111111111111111111111111"
    assert active["activity_interval"] == "m5"
    assert active["activity_count"] == 3
    assert "gt_score" not in active and "price_change_percentage" not in active


def test_tracker_pumpfun_filter_and_rank_score_order_stripping():
    fixture = _load()
    evaluated = fixture["evaluated_at"]
    contract = fixture["solana_tracker"]
    trending = normalize_tracker(contract["trending"], contract, "TRENDING_PUMPFUN", evaluated)
    top = normalize_tracker(contract["top"], contract, "TOP_PUMPFUN", evaluated)
    assert [(row["mint"], row["pool"]) for row in trending] == [(
        "MintB1111111111111111111111111111111111111",
        "PoolB1111111111111111111111111111111111111",
    )]
    assert [(row["mint"], row["pool"]) for row in top] == [(
        "MintA1111111111111111111111111111111111111",
        "PoolA1111111111111111111111111111111111111",
    )]
    assert all(set(row) == IDENTITY_KEYS for row in trending + top)

    mutated = copy.deepcopy(contract)
    mutated["trending"]["body"].reverse()
    valid = mutated["trending"]["body"][-1]
    valid["rank"] = 999999
    valid["score"] = -999999
    valid["promoted"] = False
    valid["risk"] = {"score": 100, "rugged": True, "insiders": {"count": 999}}
    valid["holders"] = 0
    valid["pools"][0]["score"] = -1
    assert normalize_tracker(mutated["trending"], mutated, "TRENDING_PUMPFUN", evaluated) == trending


def test_fail_closed_malformed_stale_and_ambiguous_cases():
    fixture = _load()
    evaluated = fixture["evaluated_at"]

    zero = copy.deepcopy(fixture["geckoterminal"])
    zero["active"]["body"]["data"]["attributes"]["transactions"]["m5"] = {"buys": 0, "sells": 0}
    with pytest.raises(ValueError, match="not_active"):
        normalize_gecko_active(zero, evaluated)

    stale = copy.deepcopy(fixture["solana_tracker"])
    # Sole pumpfun row made stale → empty contribution, not whole-body raise.
    stale["trending"]["body"][0]["pools"][0]["lastUpdated"] -= 181_000
    assert normalize_tracker(stale["trending"], stale, "TRENDING_PUMPFUN", evaluated) == []

    malformed = copy.deepcopy(fixture["solana_tracker"])
    malformed["top"]["body"][0]["pools"][0].pop("quoteToken")
    with pytest.raises(ValueError, match="missing_pool_identity"):
        normalize_tracker(malformed["top"], malformed, "TOP_PUMPFUN", evaluated)

    drift = copy.deepcopy(fixture["solana_tracker"])
    drift["trending"]["body"] = drift["trending"]["body"] * 51
    with pytest.raises(ValueError, match="malformed_or_limit_drift"):
        normalize_tracker(drift["trending"], drift, "TRENDING_PUMPFUN", evaluated)