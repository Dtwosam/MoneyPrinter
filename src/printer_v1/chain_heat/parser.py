"""Local Solana chain heat payload parser for Printer V1."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.chain_heat.contracts import ChainHeatPayloadQualityLabel
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus


NORMALIZED_FIELDS = (
    "captured_at",
    "sol_price_usd",
    "sol_change_1h",
    "sol_change_24h",
    "sol_change_7d",
    "sol_volume_24h",
    "solana_tvl_usd",
    "solana_dex_volume_24h",
    "solana_stablecoin_supply",
    "solana_active_addresses",
    "solana_tx_count_24h",
    "solana_priority_fee_context",
    "solana_congestion_context",
    "solana_new_token_count",
    "solana_hot_pair_count",
    "solana_meme_volume_24h",
    "solana_meme_liquidity_usd",
    "solana_meme_new_pair_count",
    "solana_meme_graduation_count",
    "solana_meme_failed_pair_count",
    "source_status",
    "data_quality_label",
    "snapshot_id",
    "attached_token_id",
    "attached_pair_id",
    "source_request_id",
    "source_response_id",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: datetime | str | int | float | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc)
    text = str(value).replace("Z", "+00:00")
    if text.isdigit():
        return datetime.fromtimestamp(int(text), timezone.utc)
    return datetime.fromisoformat(text).astimezone(timezone.utc)


def to_timestamp(value: datetime | str | int | float | None) -> str | None:
    parsed = parse_timestamp(value)
    return parsed.isoformat() if parsed else None


def to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def to_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(float(value))


def read_path(payload: Mapping[str, Any], *path: str) -> Any:
    current: Any = payload
    for key in path:
        if not isinstance(current, Mapping) or key not in current:
            return None
        current = current[key]
    return current


def extract_solana_asset_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    assets = payload.get("assets", {})
    if not isinstance(assets, Mapping):
        assets = {}
    solana = assets.get("solana") or payload.get("solana") or payload.get("sol") or {}
    market_data = solana.get("market_data", {}) if isinstance(solana, Mapping) else {}
    return {
        "captured_at": payload.get("captured_at") or solana.get("captured_at"),
        "sol_price_usd": to_float(
            solana.get("price_usd") or read_path(market_data, "current_price", "usd")
        ),
        "sol_change_1h": to_float(
            solana.get("change_1h")
            or solana.get("price_change_percentage_1h")
            or read_path(market_data, "price_change_percentage_1h_in_currency", "usd")
        ),
        "sol_change_24h": to_float(
            solana.get("change_24h")
            or solana.get("price_change_percentage_24h")
            or market_data.get("price_change_percentage_24h")
        ),
        "sol_change_7d": to_float(
            solana.get("change_7d")
            or solana.get("price_change_percentage_7d")
            or market_data.get("price_change_percentage_7d")
        ),
        "sol_volume_24h": to_float(
            solana.get("volume_24h") or read_path(market_data, "total_volume", "usd")
        ),
    }


def extract_solana_network_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    network = payload.get("network_context") if isinstance(payload.get("network_context"), Mapping) else payload
    return {
        "captured_at": network.get("captured_at") or payload.get("captured_at"),
        "solana_active_addresses": to_int(network.get("solana_active_addresses") or network.get("active_addresses")),
        "solana_tx_count_24h": to_int(network.get("solana_tx_count_24h") or network.get("tx_count_24h")),
        "solana_priority_fee_context": network.get("solana_priority_fee_context") or network.get("priority_fee_context"),
        "solana_congestion_context": network.get("solana_congestion_context") or network.get("congestion_context"),
        "solana_new_token_count": to_int(network.get("solana_new_token_count") or network.get("new_token_count")),
    }


def extract_solana_liquidity_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    liquidity = payload.get("liquidity_context") if isinstance(payload.get("liquidity_context"), Mapping) else payload
    return {
        "captured_at": liquidity.get("captured_at") or payload.get("captured_at"),
        "solana_tvl_usd": to_float(liquidity.get("solana_tvl_usd") or liquidity.get("tvl_usd")),
        "solana_dex_volume_24h": to_float(
            liquidity.get("solana_dex_volume_24h") or liquidity.get("dex_volume_24h")
        ),
        "solana_stablecoin_supply": to_float(
            liquidity.get("solana_stablecoin_supply") or liquidity.get("stablecoin_supply")
        ),
    }


def extract_solana_meme_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    meme = payload.get("meme_context") if isinstance(payload.get("meme_context"), Mapping) else payload
    return {
        "captured_at": meme.get("captured_at") or payload.get("captured_at"),
        "solana_hot_pair_count": to_int(meme.get("solana_hot_pair_count") or meme.get("hot_pair_count")),
        "solana_meme_volume_24h": to_float(
            meme.get("solana_meme_volume_24h") or meme.get("meme_volume_24h")
        ),
        "solana_meme_liquidity_usd": to_float(
            meme.get("solana_meme_liquidity_usd") or meme.get("meme_liquidity_usd")
        ),
        "solana_meme_new_pair_count": to_int(
            meme.get("solana_meme_new_pair_count") or meme.get("meme_new_pair_count")
        ),
        "solana_meme_graduation_count": to_int(
            meme.get("solana_meme_graduation_count") or meme.get("meme_graduation_count")
        ),
        "solana_meme_failed_pair_count": to_int(
            meme.get("solana_meme_failed_pair_count") or meme.get("meme_failed_pair_count")
        ),
    }


def normalize_chain_heat_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    normalized = {field: payload.get(field) for field in NORMALIZED_FIELDS}
    for extracted in (
        extract_solana_asset_context(payload),
        extract_solana_network_context(payload),
        extract_solana_liquidity_context(payload),
        extract_solana_meme_context(payload),
    ):
        for key, value in extracted.items():
            if normalized.get(key) is None and value is not None:
                normalized[key] = value

    normalized["captured_at"] = to_timestamp(normalized.get("captured_at"))
    normalized["source_status"] = SourceStatus(
        normalized.get("source_status") or SourceStatus.COMPLETE
    ).value
    normalized["data_quality_label"] = DataQualityLabel(
        normalized.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    ).value
    for field in (
        "sol_price_usd",
        "sol_change_1h",
        "sol_change_24h",
        "sol_change_7d",
        "sol_volume_24h",
        "solana_tvl_usd",
        "solana_dex_volume_24h",
        "solana_stablecoin_supply",
        "solana_meme_volume_24h",
        "solana_meme_liquidity_usd",
    ):
        normalized[field] = to_float(normalized.get(field))
    for field in (
        "solana_active_addresses",
        "solana_tx_count_24h",
        "solana_new_token_count",
        "solana_hot_pair_count",
        "solana_meme_new_pair_count",
        "solana_meme_graduation_count",
        "solana_meme_failed_pair_count",
        "snapshot_id",
        "attached_token_id",
        "attached_pair_id",
        "source_request_id",
        "source_response_id",
    ):
        normalized[field] = to_int(normalized.get(field))
    return normalized


def chain_heat_payload_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_time = bool(payload.get("captured_at"))
    has_asset = payload.get("sol_price_usd") is not None or payload.get("sol_change_24h") is not None
    has_network = payload.get("solana_active_addresses") is not None or payload.get("solana_tx_count_24h") is not None
    has_liquidity = payload.get("solana_tvl_usd") is not None or payload.get("solana_dex_volume_24h") is not None
    has_meme = payload.get("solana_hot_pair_count") is not None or payload.get("solana_meme_volume_24h") is not None
    return has_time and (has_asset or has_network or has_liquidity or has_meme)


def chain_heat_payload_is_stale(
    payload: Mapping[str, Any],
    now: datetime | None = None,
    stale_after_seconds: int | None = None,
) -> bool:
    captured_at = parse_timestamp(payload.get("captured_at"))
    if captured_at is None:
        return True
    current_time = now or utc_now()
    max_age = stale_after_seconds or 90 * 60
    return (current_time - captured_at).total_seconds() > max_age


def validate_chain_heat_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> ChainHeatPayloadQualityLabel:
    from printer_v1.chain_heat.classifier import classify_chain_heat_payload_quality

    return classify_chain_heat_payload_quality(normalize_chain_heat_payload(payload, now), now)
