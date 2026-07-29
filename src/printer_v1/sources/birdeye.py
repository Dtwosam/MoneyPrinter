"""Optional fixture-only Birdeye free new-listing nomination adapter.

Official contract adopted 2026-07-29: Birdeye Standard costs $0, requires an
account API key, and permits the Solana ``/defi/v2/tokens/new_listing`` route.
This module contains no network transport and never accepts a paid fallback.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.contracts import NormalizedSourceResult


BIRDEYE_SOURCE_NAME = "birdeye"
BIRDEYE_NEW_LISTING_REQUEST_KIND = "birdeye_new_listing_nomination"
BIRDEYE_NEW_LISTING_ENDPOINT = (
    "https://public-api.birdeye.so/defi/v2/tokens/new_listing"
)
BIRDEYE_STANDARD_PLAN_COST_USD = 0
BIRDEYE_STANDARD_RATE_LIMIT_PER_SECOND = 1
BIRDEYE_STANDARD_MONTHLY_COMPUTE_UNITS = 30_000
BIRDEYE_NEW_LISTING_LIMIT = 20


def normalize_birdeye_new_listing(
    payload: Mapping[str, Any],
    *,
    observed_at: str,
) -> NormalizedSourceResult:
    """Normalize a frozen Birdeye Solana new-listing response.

    Only exact token nomination fields are retained. Liquidity and listing time
    are provider facts, not pool identity, origin, safety, or admission proof.
    """
    if payload.get("fixture_status") == "failure":
        return _failure(
            str(payload.get("failure_type") or "birdeye_provider_failure"),
            str(payload.get("failure_message") or "Birdeye provider failure"),
        )
    if payload.get("fixture_status") == "rate_limited":
        return NormalizedSourceResult(
            source_name=BIRDEYE_SOURCE_NAME,
            request_kind=BIRDEYE_NEW_LISTING_REQUEST_KIND,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="birdeye_rate_limited",
            failure_message="Birdeye Standard-plan rate limit",
        )

    raw_data = payload.get("data")
    if isinstance(raw_data, Mapping):
        raw_items = raw_data.get("items") or raw_data.get("tokens")
    else:
        raw_items = raw_data
    if not isinstance(raw_items, list):
        return _failure(
            "birdeye_missing_items",
            "Birdeye new-listing response did not contain a list",
        )

    tokens: list[dict[str, Any]] = []
    seen: set[str] = set()
    for item in raw_items[:BIRDEYE_NEW_LISTING_LIMIT]:
        if not isinstance(item, Mapping):
            continue
        address = str(item.get("address") or item.get("token_address") or "").strip()
        if not address or address in seen:
            continue
        seen.add(address)
        tokens.append(
            {
                "chain": "solana",
                "mint": address,
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "liquidity_usd": item.get("liquidity"),
                "listing_time": (
                    item.get("liquidityAddedAt")
                    or item.get("liquidity_added_at")
                    or item.get("listing_time")
                ),
                "observed_at": observed_at,
                "evidence_scope": "NOMINATION_ONLY",
            }
        )
    if not tokens:
        return _failure(
            "birdeye_no_valid_solana_tokens",
            "Birdeye new-listing response contained no valid token address",
        )
    return NormalizedSourceResult(
        source_name=BIRDEYE_SOURCE_NAME,
        request_kind=BIRDEYE_NEW_LISTING_REQUEST_KIND,
        source_status=SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": BIRDEYE_SOURCE_NAME,
                "request_kind": BIRDEYE_NEW_LISTING_REQUEST_KIND,
                "tokens": tuple(tokens),
                "candidate_nomination_only": True,
                "paid_fallback_allowed": False,
                "wallet_required": False,
            }
        ),
        status_code=200,
    )


def _failure(failure_type: str, message: str) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=BIRDEYE_SOURCE_NAME,
        request_kind=BIRDEYE_NEW_LISTING_REQUEST_KIND,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=message,
    )


__all__ = [
    "BIRDEYE_SOURCE_NAME",
    "BIRDEYE_NEW_LISTING_REQUEST_KIND",
    "BIRDEYE_NEW_LISTING_ENDPOINT",
    "BIRDEYE_STANDARD_PLAN_COST_USD",
    "BIRDEYE_STANDARD_RATE_LIMIT_PER_SECOND",
    "BIRDEYE_STANDARD_MONTHLY_COMPUTE_UNITS",
    "BIRDEYE_NEW_LISTING_LIMIT",
    "normalize_birdeye_new_listing",
]
