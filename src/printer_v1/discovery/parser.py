"""Local payload parsing and normalization for Printer V1 discovery."""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.contracts.rules import PRINTER_CHAIN
from printer_v1.discovery.contracts import DiscoveryPayloadState
from printer_v1.sources.registry import SOURCE_REGISTRY


NORMALIZED_FIELDS = (
    "token_mint",
    "pair_address",
    "chain",
    "source_name",
    "symbol",
    "name",
    "dex",
    "pool_source",
    "base_token_mint",
    "quote_token_mint",
    "price_usd",
    "liquidity_usd",
    "volume_5m",
    "volume_15m",
    "volume_1h",
    "volume_24h",
    "txns_5m",
    "txns_15m",
    "txns_1h",
    "txns_24h",
    "fdv",
    "market_cap",
    "captured_at",
)

CRITICAL_FIELDS = ("token_mint", "pair_address", "chain", "source_name", "captured_at")


@dataclass(frozen=True)
class PayloadValidation:
    state: DiscoveryPayloadState
    reason: str


def validate_discovery_payload(
    source_name: str, payload: Mapping[str, Any], now: datetime | None = None
) -> PayloadValidation:
    del now
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown discovery source: {source_name}")
    if payload.get("source_status") == "STALE":
        return PayloadValidation(DiscoveryPayloadState.STALE_SOURCE_DATA, "source_status_stale")
    if payload.get("source_status") == "CONFLICTING":
        return PayloadValidation(
            DiscoveryPayloadState.CONFLICTING_SOURCE_DATA,
            "source_status_conflicting",
        )
    items = extract_candidate_items(source_name, payload)
    if not items:
        return PayloadValidation(DiscoveryPayloadState.MISSING_CRITICAL_FIELDS, "no_candidates")
    candidates = [normalize_candidate(source_name, item) for item in items]
    if any(not candidate_has_required_fields(candidate) for candidate in candidates):
        return PayloadValidation(
            DiscoveryPayloadState.MISSING_CRITICAL_FIELDS,
            "missing_critical_candidate_fields",
        )
    if any(not candidate_is_solana(candidate) for candidate in candidates):
        return PayloadValidation(DiscoveryPayloadState.UNSUPPORTED_CHAIN, "non_solana_candidate")
    if any(not candidate.get("pair_address") for candidate in candidates):
        return PayloadValidation(DiscoveryPayloadState.UNSUPPORTED_PAIR, "missing_pair")
    if any(has_missing_market_fields(candidate) for candidate in candidates):
        return PayloadValidation(DiscoveryPayloadState.PARTIAL_PAYLOAD, "market_fields_partial")
    return PayloadValidation(DiscoveryPayloadState.VALID_PAYLOAD, "valid")


def extract_candidate_items(source_name: str, payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown discovery source: {source_name}")
    for key in ("pairs", "tokens", "data", "items", "candidates"):
        value = payload.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, Mapping)]
    if any(key in payload for key in ("token_mint", "tokenAddress", "baseToken", "mint")):
        return [payload]
    return []


def normalize_candidate(source_name: str, candidate_payload: Mapping[str, Any]) -> dict[str, Any]:
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown discovery source: {source_name}")

    base_token = candidate_payload.get("baseToken") or {}
    quote_token = candidate_payload.get("quoteToken") or {}
    attributes = candidate_payload.get("attributes") or {}
    relationships = candidate_payload.get("relationships") or {}

    captured_at = first_present(
        candidate_payload,
        attributes,
        keys=("captured_at", "capturedAt", "createdAt", "created_at", "updated_at"),
    )
    normalized = {
        "token_mint": first_present(
            candidate_payload,
            keys=("token_mint", "tokenAddress", "mint", "base_token_address"),
        )
        or first_present(
            attributes,
            relationships,
            keys=("base_token_address", "baseTokenAddress", "token_mint", "mint"),
        )
        or first_present(
            base_token,
            keys=("address",),
        ),
        "pair_address": first_present(
            candidate_payload,
            keys=("pair_address", "pairAddress", "pool_address", "poolAddress"),
        )
        or first_present(
            attributes,
            keys=("pair_address", "pairAddress", "address", "pool_address", "poolAddress"),
        )
        or first_present(
            candidate_payload,
            keys=("id",),
        ),
        "chain": normalize_chain(
            first_present(candidate_payload, attributes, keys=("chain", "chainId", "network"))
        ),
        "source_name": source_name,
        "symbol": first_present(candidate_payload, attributes, base_token, keys=("symbol",)),
        "name": first_present(candidate_payload, attributes, base_token, keys=("name",)),
        "dex": first_present(candidate_payload, attributes, keys=("dex", "dexId")),
        "pool_source": first_present(candidate_payload, attributes, keys=("pool_source", "poolSource")),
        "base_token_mint": first_present(
            candidate_payload,
            attributes,
            relationships,
            base_token,
            keys=("base_token_mint", "baseTokenAddress", "base_token_address", "address"),
        ),
        "quote_token_mint": first_present(
            candidate_payload,
            attributes,
            relationships,
            quote_token,
            keys=("quote_token_mint", "quoteTokenAddress", "quote_token_address", "address"),
        ),
        "price_usd": numeric_value(candidate_payload, attributes, keys=("price_usd", "priceUsd")),
        "liquidity_usd": nested_numeric(
            candidate_payload,
            attributes,
            key_paths=(("liquidity", "usd"), ("reserve_in_usd",), ("liquidity_usd",)),
        ),
        "volume_5m": nested_numeric(candidate_payload, attributes, key_paths=(("volume", "m5"), ("volume_5m",))),
        "volume_15m": nested_numeric(candidate_payload, attributes, key_paths=(("volume", "m15"), ("volume_15m",))),
        "volume_1h": nested_numeric(candidate_payload, attributes, key_paths=(("volume", "h1"), ("volume_1h",))),
        "volume_24h": nested_numeric(candidate_payload, attributes, key_paths=(("volume", "h24"), ("volume_24h",))),
        "txns_5m": nested_int(candidate_payload, attributes, key_paths=(("txns", "m5"), ("txns_5m",))),
        "txns_15m": nested_int(candidate_payload, attributes, key_paths=(("txns", "m15"), ("txns_15m",))),
        "txns_1h": nested_int(candidate_payload, attributes, key_paths=(("txns", "h1"), ("txns_1h",))),
        "txns_24h": nested_int(candidate_payload, attributes, key_paths=(("txns", "h24"), ("txns_24h",))),
        "fdv": numeric_value(candidate_payload, attributes, keys=("fdv", "fully_diluted_valuation")),
        "market_cap": numeric_value(candidate_payload, attributes, keys=("market_cap", "marketCap")),
        "captured_at": normalize_timestamp(captured_at),
    }
    return {field: normalized.get(field) for field in NORMALIZED_FIELDS}


def normalize_candidates(source_name: str, payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    return [normalize_candidate(source_name, item) for item in extract_candidate_items(source_name, payload)]


def candidate_has_required_fields(candidate: Mapping[str, Any]) -> bool:
    return all(candidate.get(field) not in (None, "") for field in CRITICAL_FIELDS)


def candidate_is_solana(candidate: Mapping[str, Any]) -> bool:
    return candidate.get("chain") == PRINTER_CHAIN


def has_missing_market_fields(candidate: Mapping[str, Any]) -> bool:
    return any(candidate.get(field) is None for field in ("price_usd", "liquidity_usd"))


def first_present(*sources: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                return value
    return None


def normalize_chain(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).lower()
    if text in {"solana", "sol"}:
        return PRINTER_CHAIN
    return text


def normalize_timestamp(value: Any) -> str:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).isoformat()
    if value not in (None, ""):
        return str(value)
    return datetime.now(timezone.utc).isoformat()


def numeric_value(*sources: Mapping[str, Any], keys: str) -> float | None:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value not in (None, ""):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    return None
    return None


def nested_numeric(*sources: Mapping[str, Any], key_paths: tuple[tuple[str, ...], ...]) -> float | None:
    value = nested_value(*sources, key_paths=key_paths)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def nested_int(*sources: Mapping[str, Any], key_paths: tuple[tuple[str, ...], ...]) -> int | None:
    value = nested_numeric(*sources, key_paths=key_paths)
    return int(value) if value is not None else None


def nested_value(*sources: Mapping[str, Any], key_paths: tuple[tuple[str, ...], ...]) -> Any:
    for source in sources:
        for path in key_paths:
            current: Any = source
            for key in path:
                if not isinstance(current, Mapping) or key not in current:
                    current = None
                    break
                current = current[key]
            if current not in (None, ""):
                return current
    return None
