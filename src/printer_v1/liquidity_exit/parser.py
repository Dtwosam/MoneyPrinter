"""Local Liquidity + Exit payload parser for Printer V1."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.liquidity_exit.contracts import LiquidityExitPayloadQualityLabel


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
    "volume_24h",
    "txns_5m",
    "txns_15m",
    "txns_1h",
    "txns_24h",
    "expected_entry_size_usd",
    "expected_exit_size_usd",
    "estimated_entry_slippage_percent",
    "estimated_exit_slippage_percent",
    "estimated_entry_price_impact_percent",
    "estimated_exit_price_impact_percent",
    "route_available",
    "route_source",
    "quote_captured_at",
    "quote_age_seconds",
    "quote_status",
    "route_status",
    "liquidity_before_usd",
    "liquidity_after_usd",
    "liquidity_change_percent",
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


def to_bool_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "yes", "1", "available"}:
            return 1
        if lowered in {"false", "no", "0", "unavailable"}:
            return 0
    return 1 if bool(value) else 0


def extract_liquidity_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("liquidity") if isinstance(payload.get("liquidity"), Mapping) else payload
    return {
        "price_usd": to_float(context.get("price_usd")),
        "liquidity_usd": to_float(context.get("liquidity_usd") or context.get("usd")),
        "volume_5m": to_float(context.get("volume_5m")),
        "volume_15m": to_float(context.get("volume_15m")),
        "volume_1h": to_float(context.get("volume_1h")),
        "volume_24h": to_float(context.get("volume_24h")),
        "txns_5m": to_int(context.get("txns_5m")),
        "txns_15m": to_int(context.get("txns_15m")),
        "txns_1h": to_int(context.get("txns_1h")),
        "txns_24h": to_int(context.get("txns_24h")),
        "liquidity_before_usd": to_float(context.get("liquidity_before_usd")),
        "liquidity_after_usd": to_float(context.get("liquidity_after_usd")),
        "liquidity_change_percent": to_float(context.get("liquidity_change_percent")),
    }


def extract_route_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("route") if isinstance(payload.get("route"), Mapping) else payload
    return {
        "route_available": to_bool_int(context.get("route_available")),
        "route_source": context.get("route_source") or context.get("source"),
        "route_status": context.get("route_status") or context.get("status"),
    }


def extract_quote_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("quote") if isinstance(payload.get("quote"), Mapping) else payload
    return {
        "quote_captured_at": to_timestamp(
            context.get("quote_captured_at") or context.get("captured_at")
        ),
        "quote_age_seconds": to_int(context.get("quote_age_seconds")),
        "quote_status": context.get("quote_status") or context.get("status"),
    }


def extract_slippage_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("slippage") if isinstance(payload.get("slippage"), Mapping) else payload
    return {
        "expected_entry_size_usd": to_float(context.get("expected_entry_size_usd")),
        "expected_exit_size_usd": to_float(context.get("expected_exit_size_usd")),
        "estimated_entry_slippage_percent": to_float(
            context.get("estimated_entry_slippage_percent")
        ),
        "estimated_exit_slippage_percent": to_float(
            context.get("estimated_exit_slippage_percent")
        ),
    }


def extract_price_impact_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("price_impact") if isinstance(payload.get("price_impact"), Mapping) else payload
    return {
        "estimated_entry_price_impact_percent": to_float(
            context.get("estimated_entry_price_impact_percent")
        ),
        "estimated_exit_price_impact_percent": to_float(
            context.get("estimated_exit_price_impact_percent")
        ),
    }


def normalize_liquidity_exit_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    current_time = now or utc_now()
    normalized = {field: payload.get(field) for field in NORMALIZED_FIELDS}
    token = payload.get("token") if isinstance(payload.get("token"), Mapping) else payload
    pair = payload.get("pair") if isinstance(payload.get("pair"), Mapping) else payload
    normalized["token_id"] = normalized.get("token_id") or token.get("token_id")
    normalized["pair_id"] = normalized.get("pair_id") or pair.get("pair_id")
    normalized["token_mint"] = normalized.get("token_mint") or token.get("token_mint") or token.get("mint")
    normalized["pair_address"] = normalized.get("pair_address") or pair.get("pair_address")
    normalized["captured_at"] = normalized.get("captured_at") or payload.get("timestamp")

    for extracted in (
        extract_liquidity_context(payload),
        extract_route_context(payload),
        extract_quote_context(payload),
        extract_slippage_context(payload),
        extract_price_impact_context(payload),
    ):
        for key, value in extracted.items():
            if normalized.get(key) is None and value is not None:
                normalized[key] = value

    normalized["captured_at"] = to_timestamp(normalized.get("captured_at"))
    normalized["quote_captured_at"] = to_timestamp(normalized.get("quote_captured_at"))
    if normalized.get("quote_age_seconds") is None and normalized.get("quote_captured_at"):
        quote_time = parse_timestamp(normalized["quote_captured_at"])
        if quote_time is not None:
            normalized["quote_age_seconds"] = int((current_time - quote_time).total_seconds())
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
        "volume_24h",
        "expected_entry_size_usd",
        "expected_exit_size_usd",
        "estimated_entry_slippage_percent",
        "estimated_exit_slippage_percent",
        "estimated_entry_price_impact_percent",
        "estimated_exit_price_impact_percent",
        "liquidity_before_usd",
        "liquidity_after_usd",
        "liquidity_change_percent",
    ):
        normalized[field] = to_float(normalized.get(field))
    for field in ("token_id", "pair_id", "txns_5m", "txns_15m", "txns_1h", "txns_24h", "quote_age_seconds"):
        normalized[field] = to_int(normalized.get(field))
    normalized["route_available"] = to_bool_int(normalized.get("route_available"))
    return normalized


def liquidity_exit_payload_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_time = bool(payload.get("captured_at"))
    has_identity = bool(payload.get("token_id") or payload.get("token_mint"))
    has_liquidity = payload.get("liquidity_usd") is not None
    return has_time and has_identity and has_liquidity


def liquidity_exit_payload_is_stale(
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


def validate_liquidity_exit_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> LiquidityExitPayloadQualityLabel:
    from printer_v1.liquidity_exit.classifier import classify_liquidity_exit_payload_quality

    return classify_liquidity_exit_payload_quality(
        normalize_liquidity_exit_payload(payload, now),
        now,
    )
