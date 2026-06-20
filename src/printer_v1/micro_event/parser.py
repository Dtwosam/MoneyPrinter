"""Local Micro-Event payload parser for Printer V1."""

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.micro_event.contracts import MicroEventPayloadQualityLabel


NORMALIZED_FIELDS = (
    "token_id", "pair_id", "token_mint", "pair_address", "detected_at",
    "event_window_start_at", "event_window_end_at", "hold_check_15m_at",
    "price_start", "price_high", "price_low", "price_end",
    "price_change_5m_percent", "high_to_end_fade_percent",
    "max_drawdown_5m_percent", "wick_percent", "volume_5m",
    "volume_change_5m_percent", "txns_5m", "txns_change_5m_percent",
    "buys_5m", "sells_5m", "buy_volume_5m", "sell_volume_5m",
    "liquidity_start_usd", "liquidity_end_usd", "liquidity_change_5m_percent",
    "liquidity_exit_realism_label", "slippage_label", "price_impact_label",
    "route_label", "safety_status_label", "liquidity_state_label",
    "flow_direction_label", "candle_path_label", "data_quality_label",
    "source_status",
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


def percent_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return ((end - start) / start) * 100.0


def extract_micro_liquidity_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    liquidity = payload.get("liquidity") if isinstance(payload.get("liquidity"), Mapping) else payload
    return {
        "liquidity_start_usd": to_float(liquidity.get("liquidity_start_usd") or liquidity.get("start_usd")),
        "liquidity_end_usd": to_float(liquidity.get("liquidity_end_usd") or liquidity.get("end_usd")),
        "liquidity_change_5m_percent": to_float(liquidity.get("liquidity_change_5m_percent")),
        "liquidity_exit_realism_label": liquidity.get("liquidity_exit_realism_label") or liquidity.get("exit_realism_label"),
        "slippage_label": liquidity.get("slippage_label"),
        "price_impact_label": liquidity.get("price_impact_label"),
        "route_label": liquidity.get("route_label"),
        "liquidity_state_label": liquidity.get("liquidity_state_label"),
    }


def extract_micro_flow_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    flow = payload.get("flow") if isinstance(payload.get("flow"), Mapping) else payload
    return {
        "volume_5m": to_float(flow.get("volume_5m")),
        "volume_change_5m_percent": to_float(flow.get("volume_change_5m_percent")),
        "txns_5m": to_int(flow.get("txns_5m")),
        "txns_change_5m_percent": to_float(flow.get("txns_change_5m_percent")),
        "buys_5m": to_int(flow.get("buys_5m")),
        "sells_5m": to_int(flow.get("sells_5m")),
        "buy_volume_5m": to_float(flow.get("buy_volume_5m")),
        "sell_volume_5m": to_float(flow.get("sell_volume_5m")),
        "flow_direction_label": flow.get("flow_direction_label"),
    }


def extract_micro_chart_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    chart = payload.get("chart") if isinstance(payload.get("chart"), Mapping) else payload
    return {
        "price_start": to_float(chart.get("price_start") or chart.get("open")),
        "price_high": to_float(chart.get("price_high") or chart.get("high")),
        "price_low": to_float(chart.get("price_low") or chart.get("low")),
        "price_end": to_float(chart.get("price_end") or chart.get("close")),
        "price_change_5m_percent": to_float(chart.get("price_change_5m_percent")),
        "high_to_end_fade_percent": to_float(chart.get("high_to_end_fade_percent")),
        "max_drawdown_5m_percent": to_float(chart.get("max_drawdown_5m_percent")),
        "wick_percent": to_float(chart.get("wick_percent")),
        "candle_path_label": chart.get("candle_path_label"),
    }


def extract_holding_to_15m_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    hold = payload.get("hold_15m") if isinstance(payload.get("hold_15m"), Mapping) else payload
    return {
        "hold_check_15m_at": hold.get("hold_check_15m_at"),
        "held_to_15m_price_change_percent": to_float(hold.get("held_to_15m_price_change_percent")),
        "held_to_15m_liquidity_usd": to_float(hold.get("held_to_15m_liquidity_usd")),
    }


def extract_micro_event_from_token_snapshots(snapshots: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = sorted([dict(row) for row in snapshots], key=lambda row: str(row.get("captured_at") or ""))
    if not rows:
        return {}
    prices = [to_float(row.get("price_usd")) for row in rows]
    prices = [price for price in prices if price is not None]
    if not prices:
        return {}
    start = prices[0]
    high = max(prices)
    low = min(prices)
    end = prices[-1]
    first_liq = to_float(rows[0].get("liquidity_usd"))
    last_liq = to_float(rows[-1].get("liquidity_usd"))
    return {
        "token_id": rows[0].get("token_id"),
        "pair_id": rows[0].get("pair_id"),
        "detected_at": rows[-1].get("captured_at"),
        "event_window_start_at": rows[0].get("captured_at"),
        "event_window_end_at": rows[-1].get("captured_at"),
        "hold_check_15m_at": to_timestamp((parse_timestamp(rows[0].get("captured_at")) or utc_now()) + timedelta(minutes=15)),
        "price_start": start,
        "price_high": high,
        "price_low": low,
        "price_end": end,
        "price_change_5m_percent": percent_change(start, end),
        "high_to_end_fade_percent": percent_change(high, end),
        "max_drawdown_5m_percent": percent_change(start, low),
        "wick_percent": calculate_wick_percent(start, high, end),
        "volume_5m": to_float(rows[-1].get("volume_5m")),
        "txns_5m": to_int(rows[-1].get("txns_5m")),
        "liquidity_start_usd": first_liq,
        "liquidity_end_usd": last_liq,
        "liquidity_change_5m_percent": percent_change(first_liq, last_liq),
        "source_status": rows[-1].get("source_status") or SourceStatus.COMPLETE.value,
        "data_quality_label": rows[-1].get("data_quality_label") or DataQualityLabel.CLEAN_DATA.value,
    }


def calculate_wick_percent(start: float | None, high: float | None, end: float | None) -> float | None:
    runup = percent_change(start, high)
    if runup is None or runup <= 0 or high is None or end is None:
        return None
    fade = abs(percent_change(high, end) or 0.0)
    return min(100.0, fade / runup * 100.0)


def build_micro_event_payload_from_token_snapshots(
    snapshots: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    return extract_micro_event_from_token_snapshots(snapshots)


def normalize_micro_event_payload(payload: Mapping[str, Any], now: datetime | None = None) -> dict[str, Any]:
    del now
    normalized = {field: payload.get(field) for field in NORMALIZED_FIELDS}
    token = payload.get("token") if isinstance(payload.get("token"), Mapping) else payload
    pair = payload.get("pair") if isinstance(payload.get("pair"), Mapping) else payload
    normalized["token_id"] = normalized.get("token_id") or token.get("token_id")
    normalized["pair_id"] = normalized.get("pair_id") or pair.get("pair_id")
    normalized["token_mint"] = normalized.get("token_mint") or token.get("token_mint") or token.get("mint")
    normalized["pair_address"] = normalized.get("pair_address") or pair.get("pair_address")
    normalized["detected_at"] = normalized.get("detected_at") or payload.get("captured_at") or payload.get("timestamp")
    for extracted in (
        extract_micro_chart_context(payload),
        extract_micro_flow_context(payload),
        extract_micro_liquidity_context(payload),
        extract_holding_to_15m_context(payload),
    ):
        for key, value in extracted.items():
            if normalized.get(key) is None and value is not None:
                normalized[key] = value
    for timestamp_field in ("detected_at", "event_window_start_at", "event_window_end_at", "hold_check_15m_at"):
        normalized[timestamp_field] = to_timestamp(normalized.get(timestamp_field))
    for field in (
        "price_start", "price_high", "price_low", "price_end", "price_change_5m_percent",
        "high_to_end_fade_percent", "max_drawdown_5m_percent", "wick_percent", "volume_5m",
        "volume_change_5m_percent", "buy_volume_5m", "sell_volume_5m",
        "liquidity_start_usd", "liquidity_end_usd", "liquidity_change_5m_percent",
    ):
        normalized[field] = to_float(normalized.get(field))
    for field in ("token_id", "pair_id", "txns_5m", "buys_5m", "sells_5m"):
        normalized[field] = to_int(normalized.get(field))
    start = normalized.get("price_start")
    high = normalized.get("price_high")
    low = normalized.get("price_low")
    end = normalized.get("price_end")
    normalized["price_change_5m_percent"] = normalized.get("price_change_5m_percent") or percent_change(start, end)
    normalized["high_to_end_fade_percent"] = normalized.get("high_to_end_fade_percent") or percent_change(high, end)
    normalized["max_drawdown_5m_percent"] = normalized.get("max_drawdown_5m_percent") or percent_change(start, low)
    normalized["wick_percent"] = normalized.get("wick_percent") or calculate_wick_percent(start, high, end)
    normalized["liquidity_change_5m_percent"] = normalized.get("liquidity_change_5m_percent") or percent_change(
        normalized.get("liquidity_start_usd"),
        normalized.get("liquidity_end_usd"),
    )
    normalized["source_status"] = SourceStatus(normalized.get("source_status") or SourceStatus.COMPLETE).value
    normalized["data_quality_label"] = DataQualityLabel(normalized.get("data_quality_label") or DataQualityLabel.CLEAN_DATA).value
    return normalized


def micro_event_payload_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_time = bool(payload.get("detected_at") and payload.get("event_window_start_at") and payload.get("event_window_end_at"))
    has_identity = bool(payload.get("token_id") or payload.get("token_mint"))
    has_price_path = all(payload.get(field) is not None for field in ("price_start", "price_high", "price_low", "price_end"))
    return has_time and has_identity and has_price_path


def micro_event_payload_is_stale(
    payload: Mapping[str, Any],
    now: datetime | None = None,
    stale_after_seconds: int | None = None,
) -> bool:
    detected_at = parse_timestamp(payload.get("detected_at"))
    if detected_at is None:
        return True
    max_age = stale_after_seconds or 60 * 60
    return ((now or utc_now()) - detected_at).total_seconds() > max_age


def validate_micro_event_payload(payload: Mapping[str, Any], now: datetime | None = None) -> MicroEventPayloadQualityLabel:
    from printer_v1.micro_event.classifier import classify_micro_event_payload_quality

    return classify_micro_event_payload_quality(normalize_micro_event_payload(payload, now), now)
