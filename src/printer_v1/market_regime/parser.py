"""Local market context payload parser for Printer V1."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.market_regime.contracts import MarketPayloadQualityLabel


NORMALIZED_FIELDS = (
    "captured_at",
    "btc_price_usd",
    "btc_change_1h",
    "btc_change_24h",
    "btc_change_7d",
    "eth_price_usd",
    "eth_change_24h",
    "eth_change_7d",
    "sol_price_usd",
    "sol_change_1h",
    "sol_change_24h",
    "sol_change_7d",
    "sol_volume_24h",
    "fear_greed_value",
    "fear_greed_label",
    "fear_greed_previous_value",
    "fear_greed_previous_label",
    "solana_tvl_usd",
    "solana_dex_volume_context",
    "stablecoin_context",
    "tracked_solana_meme_volume",
    "tracked_solana_meme_liquidity",
    "tracked_solana_hot_pair_count",
    "tracked_solana_new_pair_count",
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


def extract_fear_greed_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    current = data[0] if isinstance(data, list) and data else payload.get("fear_greed", {})
    previous = data[1] if isinstance(data, list) and len(data) > 1 else payload.get(
        "fear_greed_previous",
        {},
    )
    if not isinstance(current, Mapping):
        current = {}
    if not isinstance(previous, Mapping):
        previous = {}
    return {
        "fear_greed_value": to_int(current.get("value")),
        "fear_greed_label": current.get("value_classification") or current.get("label"),
        "fear_greed_previous_value": to_int(previous.get("value")),
        "fear_greed_previous_label": previous.get("value_classification") or previous.get("label"),
        "captured_at": current.get("timestamp") or payload.get("captured_at"),
    }


def asset_context(asset: Mapping[str, Any]) -> dict[str, Any]:
    market_data = asset.get("market_data", {}) if isinstance(asset, Mapping) else {}
    return {
        "price": asset.get("price_usd") or read_path(market_data, "current_price", "usd"),
        "change_1h": asset.get("change_1h")
        or asset.get("price_change_percentage_1h")
        or market_data.get("price_change_percentage_1h_in_currency", {}).get("usd"),
        "change_24h": asset.get("change_24h")
        or asset.get("price_change_percentage_24h")
        or market_data.get("price_change_percentage_24h"),
        "change_7d": asset.get("change_7d")
        or asset.get("price_change_percentage_7d")
        or market_data.get("price_change_percentage_7d"),
        "volume_24h": asset.get("volume_24h")
        or read_path(market_data, "total_volume", "usd"),
    }


def extract_major_asset_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    assets = payload.get("assets", {})
    if not isinstance(assets, Mapping):
        assets = {}
    bitcoin = assets.get("bitcoin") or payload.get("bitcoin") or payload.get("btc") or {}
    ethereum = assets.get("ethereum") or payload.get("ethereum") or payload.get("eth") or {}
    solana = assets.get("solana") or payload.get("solana") or payload.get("sol") or {}
    btc = asset_context(bitcoin)
    eth = asset_context(ethereum)
    sol = asset_context(solana)
    return {
        "btc_price_usd": to_float(btc["price"]),
        "btc_change_1h": to_float(btc["change_1h"]),
        "btc_change_24h": to_float(btc["change_24h"]),
        "btc_change_7d": to_float(btc["change_7d"]),
        "eth_price_usd": to_float(eth["price"]),
        "eth_change_24h": to_float(eth["change_24h"]),
        "eth_change_7d": to_float(eth["change_7d"]),
        "sol_price_usd": to_float(sol["price"]),
        "sol_change_1h": to_float(sol["change_1h"]),
        "sol_change_24h": to_float(sol["change_24h"]),
        "sol_change_7d": to_float(sol["change_7d"]),
        "sol_volume_24h": to_float(sol["volume_24h"]),
        "captured_at": payload.get("captured_at"),
    }


def extract_solana_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    solana = payload.get("solana_context") if isinstance(payload.get("solana_context"), Mapping) else payload
    return {
        "solana_tvl_usd": to_float(solana.get("solana_tvl_usd") or solana.get("tvl_usd")),
        "solana_dex_volume_context": solana.get("solana_dex_volume_context")
        or solana.get("dex_volume_context"),
        "stablecoin_context": solana.get("stablecoin_context"),
        "tracked_solana_meme_volume": to_float(solana.get("tracked_solana_meme_volume")),
        "tracked_solana_meme_liquidity": to_float(
            solana.get("tracked_solana_meme_liquidity")
        ),
        "tracked_solana_hot_pair_count": to_int(
            solana.get("tracked_solana_hot_pair_count")
        ),
        "tracked_solana_new_pair_count": to_int(
            solana.get("tracked_solana_new_pair_count")
        ),
        "captured_at": solana.get("captured_at") or payload.get("captured_at"),
    }


def normalize_market_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    normalized = {field: payload.get(field) for field in NORMALIZED_FIELDS}
    for extracted in (
        extract_fear_greed_context(payload),
        extract_major_asset_context(payload),
        extract_solana_context(payload),
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
        "btc_price_usd",
        "btc_change_1h",
        "btc_change_24h",
        "btc_change_7d",
        "eth_price_usd",
        "eth_change_24h",
        "eth_change_7d",
        "sol_price_usd",
        "sol_change_1h",
        "sol_change_24h",
        "sol_change_7d",
        "sol_volume_24h",
        "solana_tvl_usd",
        "tracked_solana_meme_volume",
        "tracked_solana_meme_liquidity",
    ):
        normalized[field] = to_float(normalized.get(field))
    for field in (
        "fear_greed_value",
        "fear_greed_previous_value",
        "tracked_solana_hot_pair_count",
        "tracked_solana_new_pair_count",
        "snapshot_id",
        "attached_token_id",
        "attached_pair_id",
        "source_request_id",
        "source_response_id",
    ):
        normalized[field] = to_int(normalized.get(field))
    return normalized


def market_payload_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_time = bool(payload.get("captured_at"))
    has_btc_or_sol = payload.get("btc_price_usd") is not None or payload.get("sol_price_usd") is not None
    has_fear_greed = payload.get("fear_greed_value") is not None or payload.get("fear_greed_label")
    return has_time and (has_btc_or_sol or has_fear_greed)


def market_payload_is_stale(
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


def validate_market_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> MarketPayloadQualityLabel:
    from printer_v1.market_regime.classifier import classify_market_payload_quality

    return classify_market_payload_quality(normalize_market_payload(payload, now), now)
