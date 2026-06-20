"""Local Chart / Volatility payload parser for Printer V1."""

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping

from printer_v1.chart_volatility.contracts import ChartPayloadQualityLabel
from printer_v1.contracts.enums import DataQualityLabel, SourceStatus


NORMALIZED_FIELDS = (
    "token_id",
    "pair_id",
    "token_mint",
    "pair_address",
    "captured_at",
    "window_start_at",
    "window_end_at",
    "price_open",
    "price_high",
    "price_low",
    "price_close",
    "price_change_percent",
    "max_runup_percent",
    "max_drawdown_percent",
    "recovery_from_low_percent",
    "high_to_close_fade_percent",
    "open_to_low_drop_percent",
    "volatility_percent",
    "candle_count",
    "green_candle_count",
    "red_candle_count",
    "flat_candle_count",
    "largest_green_candle_percent",
    "largest_red_candle_percent",
    "consecutive_green_candles",
    "consecutive_red_candles",
    "higher_high_count",
    "lower_low_count",
    "range_high",
    "range_low",
    "range_width_percent",
    "breakout_percent",
    "breakdown_percent",
    "round_trip_percent",
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


def percent_change(start: float | None, end: float | None) -> float | None:
    if start is None or end is None or start == 0:
        return None
    return ((end - start) / start) * 100.0


def extract_ohlc_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    ohlc = payload.get("ohlc") if isinstance(payload.get("ohlc"), Mapping) else payload
    return {
        "price_open": to_float(ohlc.get("price_open") or ohlc.get("open")),
        "price_high": to_float(ohlc.get("price_high") or ohlc.get("high")),
        "price_low": to_float(ohlc.get("price_low") or ohlc.get("low")),
        "price_close": to_float(ohlc.get("price_close") or ohlc.get("close")),
        "window_start_at": ohlc.get("window_start_at") or ohlc.get("start_at"),
        "window_end_at": ohlc.get("window_end_at") or ohlc.get("end_at"),
    }


def extract_candle_path_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    candles = payload.get("candles") if isinstance(payload.get("candles"), Mapping) else payload
    return {
        "candle_count": to_int(candles.get("candle_count")),
        "green_candle_count": to_int(candles.get("green_candle_count")),
        "red_candle_count": to_int(candles.get("red_candle_count")),
        "flat_candle_count": to_int(candles.get("flat_candle_count")),
        "largest_green_candle_percent": to_float(candles.get("largest_green_candle_percent")),
        "largest_red_candle_percent": to_float(candles.get("largest_red_candle_percent")),
        "consecutive_green_candles": to_int(candles.get("consecutive_green_candles")),
        "consecutive_red_candles": to_int(candles.get("consecutive_red_candles")),
        "higher_high_count": to_int(candles.get("higher_high_count")),
        "lower_low_count": to_int(candles.get("lower_low_count")),
    }


def extract_chart_from_token_snapshots(snapshots: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    rows = sorted(
        [dict(row) for row in snapshots],
        key=lambda row: str(row.get("captured_at") or ""),
    )
    if not rows:
        return {}
    prices = [to_float(row.get("price_usd")) for row in rows]
    prices = [price for price in prices if price is not None]
    if not prices:
        return {}
    deltas = [
        percent_change(prices[index - 1], prices[index])
        for index in range(1, len(prices))
    ]
    deltas = [delta for delta in deltas if delta is not None]
    green = [delta for delta in deltas if delta > 0.05]
    red = [delta for delta in deltas if delta < -0.05]
    flat = [delta for delta in deltas if -0.05 <= delta <= 0.05]
    high = max(prices)
    low = min(prices)
    open_price = prices[0]
    close = prices[-1]
    max_runup = percent_change(open_price, high)
    max_drawdown = percent_change(open_price, low)
    return {
        "token_id": rows[0].get("token_id"),
        "pair_id": rows[0].get("pair_id"),
        "captured_at": rows[-1].get("captured_at"),
        "window_start_at": rows[0].get("captured_at"),
        "window_end_at": rows[-1].get("captured_at"),
        "price_open": open_price,
        "price_high": high,
        "price_low": low,
        "price_close": close,
        "price_change_percent": percent_change(open_price, close),
        "max_runup_percent": max_runup,
        "max_drawdown_percent": max_drawdown,
        "recovery_from_low_percent": percent_change(low, close),
        "high_to_close_fade_percent": percent_change(high, close),
        "open_to_low_drop_percent": max_drawdown,
        "volatility_percent": percent_change(low, high),
        "candle_count": len(rows),
        "green_candle_count": len(green),
        "red_candle_count": len(red),
        "flat_candle_count": len(flat),
        "largest_green_candle_percent": max(green) if green else 0.0,
        "largest_red_candle_percent": min(red) if red else 0.0,
        "consecutive_green_candles": longest_run(deltas, positive=True),
        "consecutive_red_candles": longest_run(deltas, positive=False),
        "higher_high_count": count_higher_highs(prices),
        "lower_low_count": count_lower_lows(prices),
        "range_high": high,
        "range_low": low,
        "range_width_percent": percent_change(low, high),
        "round_trip_percent": calculate_round_trip(open_price, high, close),
        "source_status": rows[-1].get("source_status") or SourceStatus.COMPLETE.value,
        "data_quality_label": rows[-1].get("data_quality_label") or DataQualityLabel.CLEAN_DATA.value,
    }


def longest_run(values: list[float], *, positive: bool) -> int:
    best = 0
    current = 0
    for value in values:
        matches = value > 0.05 if positive else value < -0.05
        current = current + 1 if matches else 0
        best = max(best, current)
    return best


def count_higher_highs(prices: list[float]) -> int:
    count = 0
    previous = prices[0] if prices else None
    for price in prices[1:]:
        if previous is not None and price > previous:
            count += 1
        previous = max(previous, price) if previous is not None else price
    return count


def count_lower_lows(prices: list[float]) -> int:
    count = 0
    previous = prices[0] if prices else None
    for price in prices[1:]:
        if previous is not None and price < previous:
            count += 1
        previous = min(previous, price) if previous is not None else price
    return count


def calculate_round_trip(open_price: float | None, high: float | None, close: float | None) -> float | None:
    runup = percent_change(open_price, high)
    fade = percent_change(high, close)
    if runup is None or fade is None or runup <= 0:
        return None
    return min(100.0, abs(fade) / runup * 100.0)


def build_chart_payload_from_token_snapshots(
    snapshots: Iterable[Mapping[str, Any]],
    now: datetime | None = None,
) -> dict[str, Any]:
    del now
    return extract_chart_from_token_snapshots(snapshots)


def normalize_chart_payload(
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

    for extracted in (extract_ohlc_context(payload), extract_candle_path_context(payload)):
        for key, value in extracted.items():
            if normalized.get(key) is None and value is not None:
                normalized[key] = value

    for timestamp_field in ("captured_at", "window_start_at", "window_end_at"):
        normalized[timestamp_field] = to_timestamp(normalized.get(timestamp_field))

    for field in (
        "price_open",
        "price_high",
        "price_low",
        "price_close",
        "price_change_percent",
        "max_runup_percent",
        "max_drawdown_percent",
        "recovery_from_low_percent",
        "high_to_close_fade_percent",
        "open_to_low_drop_percent",
        "volatility_percent",
        "largest_green_candle_percent",
        "largest_red_candle_percent",
        "range_high",
        "range_low",
        "range_width_percent",
        "breakout_percent",
        "breakdown_percent",
        "round_trip_percent",
    ):
        normalized[field] = to_float(normalized.get(field))

    for field in (
        "token_id",
        "pair_id",
        "candle_count",
        "green_candle_count",
        "red_candle_count",
        "flat_candle_count",
        "consecutive_green_candles",
        "consecutive_red_candles",
        "higher_high_count",
        "lower_low_count",
    ):
        normalized[field] = to_int(normalized.get(field))

    open_price = normalized.get("price_open")
    high = normalized.get("price_high")
    low = normalized.get("price_low")
    close = normalized.get("price_close")
    normalized["price_change_percent"] = normalized.get("price_change_percent") or percent_change(open_price, close)
    normalized["max_runup_percent"] = normalized.get("max_runup_percent") or percent_change(open_price, high)
    normalized["max_drawdown_percent"] = normalized.get("max_drawdown_percent") or percent_change(open_price, low)
    normalized["recovery_from_low_percent"] = normalized.get("recovery_from_low_percent") or percent_change(low, close)
    normalized["high_to_close_fade_percent"] = normalized.get("high_to_close_fade_percent") or percent_change(high, close)
    normalized["open_to_low_drop_percent"] = normalized.get("open_to_low_drop_percent") or percent_change(open_price, low)
    normalized["volatility_percent"] = normalized.get("volatility_percent") or percent_change(low, high)
    normalized["range_high"] = normalized.get("range_high") or high
    normalized["range_low"] = normalized.get("range_low") or low
    normalized["range_width_percent"] = normalized.get("range_width_percent") or percent_change(low, high)
    normalized["round_trip_percent"] = normalized.get("round_trip_percent") or calculate_round_trip(open_price, high, close)
    normalized["source_status"] = SourceStatus(
        normalized.get("source_status") or SourceStatus.COMPLETE
    ).value
    normalized["data_quality_label"] = DataQualityLabel(
        normalized.get("data_quality_label") or DataQualityLabel.CLEAN_DATA
    ).value
    return normalized


def chart_payload_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_time = bool(payload.get("captured_at") and payload.get("window_start_at") and payload.get("window_end_at"))
    has_identity = bool(payload.get("token_id") or payload.get("token_mint"))
    has_price_path = all(
        payload.get(field) is not None
        for field in ("price_open", "price_high", "price_low", "price_close")
    )
    return has_time and has_identity and has_price_path


def chart_payload_is_stale(
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


def validate_chart_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> ChartPayloadQualityLabel:
    from printer_v1.chart_volatility.classifier import classify_chart_payload_quality

    return classify_chart_payload_quality(normalize_chart_payload(payload, now), now)
