"""Local Trading Flow payload parser for Printer V1."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.trading_flow.contracts import TradingFlowPayloadQualityLabel


NORMALIZED_FIELDS = (
    "token_id",
    "pair_id",
    "token_mint",
    "pair_address",
    "captured_at",
    "price_usd",
    "liquidity_usd",
    "volume_5m",
    "volume_15m",
    "volume_1h",
    "volume_4h",
    "volume_24h",
    "txns_5m",
    "txns_15m",
    "txns_1h",
    "txns_4h",
    "txns_24h",
    "buys_5m",
    "sells_5m",
    "buys_15m",
    "sells_15m",
    "buys_1h",
    "sells_1h",
    "buys_4h",
    "sells_4h",
    "buys_24h",
    "sells_24h",
    "buy_volume_5m",
    "sell_volume_5m",
    "buy_volume_15m",
    "sell_volume_15m",
    "buy_volume_1h",
    "sell_volume_1h",
    "buy_volume_4h",
    "sell_volume_4h",
    "buy_volume_24h",
    "sell_volume_24h",
    "unique_wallets_5m",
    "unique_wallets_15m",
    "unique_wallets_1h",
    "unique_wallets_24h",
    "new_wallets_5m",
    "new_wallets_15m",
    "repeat_wallets_5m",
    "repeat_wallets_15m",
    "source_status",
    "data_quality_label",
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


def extract_tx_flow_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    tx = payload.get("txns") if isinstance(payload.get("txns"), Mapping) else payload
    return {
        "txns_5m": to_int(tx.get("txns_5m") or tx.get("m5")),
        "txns_15m": to_int(tx.get("txns_15m") or tx.get("m15")),
        "txns_1h": to_int(tx.get("txns_1h") or tx.get("h1")),
        "txns_4h": to_int(tx.get("txns_4h") or tx.get("h4")),
        "txns_24h": to_int(tx.get("txns_24h") or tx.get("h24")),
        "buys_5m": to_int(tx.get("buys_5m") or tx.get("m5_buys")),
        "sells_5m": to_int(tx.get("sells_5m") or tx.get("m5_sells")),
        "buys_15m": to_int(tx.get("buys_15m") or tx.get("m15_buys")),
        "sells_15m": to_int(tx.get("sells_15m") or tx.get("m15_sells")),
        "buys_1h": to_int(tx.get("buys_1h") or tx.get("h1_buys")),
        "sells_1h": to_int(tx.get("sells_1h") or tx.get("h1_sells")),
        "buys_4h": to_int(tx.get("buys_4h") or tx.get("h4_buys")),
        "sells_4h": to_int(tx.get("sells_4h") or tx.get("h4_sells")),
        "buys_24h": to_int(tx.get("buys_24h") or tx.get("h24_buys")),
        "sells_24h": to_int(tx.get("sells_24h") or tx.get("h24_sells")),
    }


def extract_volume_flow_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    volume = payload.get("volume") if isinstance(payload.get("volume"), Mapping) else payload
    return {
        "volume_5m": to_float(volume.get("volume_5m") or volume.get("m5")),
        "volume_15m": to_float(volume.get("volume_15m") or volume.get("m15")),
        "volume_1h": to_float(volume.get("volume_1h") or volume.get("h1")),
        "volume_4h": to_float(volume.get("volume_4h") or volume.get("h4")),
        "volume_24h": to_float(volume.get("volume_24h") or volume.get("h24")),
        "buy_volume_5m": to_float(volume.get("buy_volume_5m")),
        "sell_volume_5m": to_float(volume.get("sell_volume_5m")),
        "buy_volume_15m": to_float(volume.get("buy_volume_15m")),
        "sell_volume_15m": to_float(volume.get("sell_volume_15m")),
        "buy_volume_1h": to_float(volume.get("buy_volume_1h")),
        "sell_volume_1h": to_float(volume.get("sell_volume_1h")),
        "buy_volume_4h": to_float(volume.get("buy_volume_4h")),
        "sell_volume_4h": to_float(volume.get("sell_volume_4h")),
        "buy_volume_24h": to_float(volume.get("buy_volume_24h")),
        "sell_volume_24h": to_float(volume.get("sell_volume_24h")),
    }


def extract_wallet_participation_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    wallets = payload.get("wallets") if isinstance(payload.get("wallets"), Mapping) else payload
    return {
        "unique_wallets_5m": to_int(wallets.get("unique_wallets_5m")),
        "unique_wallets_15m": to_int(wallets.get("unique_wallets_15m")),
        "unique_wallets_1h": to_int(wallets.get("unique_wallets_1h")),
        "unique_wallets_24h": to_int(wallets.get("unique_wallets_24h")),
        "new_wallets_5m": to_int(wallets.get("new_wallets_5m")),
        "new_wallets_15m": to_int(wallets.get("new_wallets_15m")),
        "repeat_wallets_5m": to_int(wallets.get("repeat_wallets_5m")),
        "repeat_wallets_15m": to_int(wallets.get("repeat_wallets_15m")),
    }


def extract_flow_from_token_snapshot(payload: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "token_id": payload.get("token_id"),
        "pair_id": payload.get("pair_id"),
        "captured_at": payload.get("captured_at"),
        "price_usd": payload.get("price_usd"),
        "liquidity_usd": payload.get("liquidity_usd"),
        "volume_5m": payload.get("volume_5m"),
        "volume_15m": payload.get("volume_15m"),
        "volume_1h": payload.get("volume_1h"),
        "volume_4h": payload.get("volume_4h"),
        "volume_24h": payload.get("volume_24h"),
        "txns_5m": payload.get("txns_5m"),
        "txns_15m": payload.get("txns_15m"),
        "txns_1h": payload.get("txns_1h"),
        "txns_4h": payload.get("txns_4h"),
        "txns_24h": payload.get("txns_24h"),
    }


def normalize_trading_flow_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    normalized = {field: payload.get(field) for field in NORMALIZED_FIELDS}
    token = payload.get("token") if isinstance(payload.get("token"), Mapping) else payload
    pair = payload.get("pair") if isinstance(payload.get("pair"), Mapping) else payload
    normalized["token_id"] = normalized.get("token_id") or token.get("token_id")
    normalized["pair_id"] = normalized.get("pair_id") or pair.get("pair_id")
    normalized["token_mint"] = normalized.get("token_mint") or token.get("token_mint") or token.get("mint")
    normalized["pair_address"] = normalized.get("pair_address") or pair.get("pair_address")
    normalized["captured_at"] = normalized.get("captured_at") or payload.get("timestamp")

    for extracted in (
        extract_flow_from_token_snapshot(payload),
        extract_tx_flow_context(payload),
        extract_volume_flow_context(payload),
        extract_wallet_participation_context(payload),
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
        "price_usd",
        "liquidity_usd",
        "volume_5m",
        "volume_15m",
        "volume_1h",
        "volume_4h",
        "volume_24h",
        "buy_volume_5m",
        "sell_volume_5m",
        "buy_volume_15m",
        "sell_volume_15m",
        "buy_volume_1h",
        "sell_volume_1h",
        "buy_volume_4h",
        "sell_volume_4h",
        "buy_volume_24h",
        "sell_volume_24h",
    ):
        normalized[field] = to_float(normalized.get(field))
    for field in (
        "token_id",
        "pair_id",
        "txns_5m",
        "txns_15m",
        "txns_1h",
        "txns_4h",
        "txns_24h",
        "buys_5m",
        "sells_5m",
        "buys_15m",
        "sells_15m",
        "buys_1h",
        "sells_1h",
        "buys_4h",
        "sells_4h",
        "buys_24h",
        "sells_24h",
        "unique_wallets_5m",
        "unique_wallets_15m",
        "unique_wallets_1h",
        "unique_wallets_24h",
        "new_wallets_5m",
        "new_wallets_15m",
        "repeat_wallets_5m",
        "repeat_wallets_15m",
    ):
        normalized[field] = to_int(normalized.get(field))
    return normalized


def trading_flow_payload_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_time = bool(payload.get("captured_at"))
    has_identity = bool(payload.get("token_id") or payload.get("token_mint"))
    has_flow = any(
        payload.get(field) is not None
        for field in (
            "volume_5m",
            "volume_15m",
            "txns_5m",
            "txns_15m",
            "buys_5m",
            "sells_5m",
            "buy_volume_5m",
            "sell_volume_5m",
        )
    )
    return has_time and has_identity and has_flow


def trading_flow_payload_is_stale(
    payload: Mapping[str, Any],
    now: datetime | None = None,
    stale_after_seconds: int | None = None,
) -> bool:
    captured_at = parse_timestamp(payload.get("captured_at"))
    if captured_at is None:
        return True
    current_time = now or utc_now()
    max_age = stale_after_seconds or 60 * 60
    return (current_time - captured_at).total_seconds() > max_age


def validate_trading_flow_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> TradingFlowPayloadQualityLabel:
    from printer_v1.trading_flow.classifier import classify_trading_flow_payload_quality

    return classify_trading_flow_payload_quality(
        normalize_trading_flow_payload(payload, now),
        now,
    )
