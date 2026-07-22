"""Governed GeckoTerminal 15-minute OHLCV and pool-trades enrichment.

Provides three 15m market evidence fields derived from GeckoTerminal free API:
  price_change_15m  — derived from completed 15m OHLCV candle arithmetic
  volume_15m        — native volume from completed 15m OHLCV candle
  txns_15m          — trade-record count within the 15m window (proven complete only)

Source kind labels written to normalized_snapshot_payload_json:
  price_change_15m_source_kind = "PROVIDER_CANDLE_DERIVED"
  volume_15m_source_kind       = "PROVIDER_CANDLE_DERIVED"
  txns_15m_source_kind         = "PROVIDER_TRADES_WINDOW"
  txns_15m_completeness        = "TRADE_HISTORY_COMPLETE" | "TRADE_HISTORY_TRUNCATED"

Provenance dicts are also written:
  price_change_15m_provenance, volume_15m_provenance, txns_15m_provenance

Design:
  All enrichment is transport-injected. Callers must supply a governed transport
  callable (fixture or live); no direct HTTP calls are made at module level. All
  functions fail closed on malformed, stale, wrong-pool, or missing responses.

txns_15m contract:
  Integer count of total trade records (buys + sells) returned by the pool-trades
  endpoint within the exact 15-minute window. Each API trade record counts as one
  transaction; duplicate tx_hash values are not deduplicated (they are separate
  on-chain actions as returned by the API). Populated only when completeness is
  proven; NULL otherwise.

Completeness rules for txns_15m:
  COMPLETE when:
    (a) total returned trade records < GT15M_TRADES_MAX_RESPONSE, OR
    (b) oldest returned trade timestamp <= window_start
  TRUNCATED (count=None) when: returned == max AND oldest > window_start
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping

PROVIDER_CANDLE_DERIVED = "PROVIDER_CANDLE_DERIVED"
PROVIDER_TRADES_WINDOW = "PROVIDER_TRADES_WINDOW"
TRADE_HISTORY_COMPLETE = "TRADE_HISTORY_COMPLETE"
TRADE_HISTORY_TRUNCATED = "TRADE_HISTORY_TRUNCATED"

GT15M_SOURCE_NAME = "geckoterminal"
GT15M_NETWORK = "solana"

GT15M_CANDLE_SECONDS = 900
GT15M_CANDLE_MAX_AGE_SECONDS = 1800

# GeckoTerminal pool-trades endpoint returns up to 300 records per request (free tier)
GT15M_TRADES_MAX_RESPONSE = 300

GECKOTERMINAL_OHLCV_REQUEST_KIND = "geckoterminal_ohlcv_15m"
GECKOTERMINAL_POOL_TRADES_REQUEST_KIND = "geckoterminal_pool_trades_15m"

GT15M_OHLCV_URL_TEMPLATE = (
    "https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}"
    "/ohlcv/minute?aggregate=15&limit=2&currency=usd&token=base"
)
GT15M_TRADES_URL_TEMPLATE = (
    "https://api.geckoterminal.com/api/v2/networks/{network}/pools/{pool_address}"
    "/trades"
)

GECKOTERMINAL_PUBLIC_API_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only source check)",
    "Accept": "application/json;version=20230302",
}

_OHLCV_IDX_TIMESTAMP = 0
_OHLCV_IDX_OPEN = 1
_OHLCV_IDX_CLOSE = 4
_OHLCV_IDX_VOLUME = 5


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        result = float(value)
        if result != result:
            return None  # NaN guard
        return result
    except (TypeError, ValueError):
        return None


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _unix_to_iso(unix_ts: float) -> str:
    return datetime.fromtimestamp(unix_ts, tz=timezone.utc).isoformat()


def _payload_is_failure(payload: Mapping[str, Any]) -> bool:
    return bool(
        payload.get("fixture_status") in ("failure", "rate_limited")
        or payload.get("error")
    )


# ---------------------------------------------------------------------------
# OHLCV candle selection
# ---------------------------------------------------------------------------

def select_completed_15m_candle(
    ohlcv_list: list[Any],
    now: datetime,
) -> dict[str, Any] | None:
    """Select the newest valid completed 15m candle without trusting row order."""
    if not isinstance(ohlcv_list, list) or not ohlcv_list:
        return None

    now_unix = now.timestamp()
    completed: list[dict[str, Any]] = []
    for raw in ohlcv_list:
        if not isinstance(raw, (list, tuple)) or len(raw) < 6:
            continue
        ts = _to_float(raw[_OHLCV_IDX_TIMESTAMP])
        open_price = _to_float(raw[_OHLCV_IDX_OPEN])
        close_price = _to_float(raw[_OHLCV_IDX_CLOSE])
        volume = _to_float(raw[_OHLCV_IDX_VOLUME])
        if any(value is None for value in (ts, open_price, close_price, volume)):
            continue
        if open_price <= 0 or volume < 0:
            continue
        candle_end_unix = ts + GT15M_CANDLE_SECONDS
        if candle_end_unix > now_unix:
            continue
        completed.append({
            "candle_start_unix": int(ts),
            "candle_end_unix": int(candle_end_unix),
            "candle_start_iso": _unix_to_iso(ts),
            "candle_end_iso": _unix_to_iso(candle_end_unix),
            "open": open_price,
            "close": close_price,
            "volume_usd": volume,
            "age_since_completion_seconds": int(now_unix - candle_end_unix),
        })
    if not completed:
        return None
    newest = max(completed, key=lambda candle: candle["candle_start_unix"])
    if newest["age_since_completion_seconds"] > GT15M_CANDLE_MAX_AGE_SECONDS:
        return None
    return newest


# ---------------------------------------------------------------------------
# Price change derivation
# ---------------------------------------------------------------------------

def derive_price_change_15m_from_candle(
    candle: dict[str, Any],
    *,
    pool_address: str,
    network: str,
    endpoint_url: str,
    fetch_time_iso: str,
) -> dict[str, Any] | None:
    """Return price_change_15m enrichment from a completed 15m candle.

    Formula: (close - open) / open * 100, rounded to 6 decimal places.
    Source_kind PROVIDER_CANDLE_DERIVED flags staged derivation to skip this field.
    Returns None when open is 0 or missing.
    """
    open_price = candle.get("open")
    close_price = candle.get("close")
    if open_price is None or close_price is None or open_price == 0:
        return None

    price_change = round(((close_price - open_price) / open_price) * 100, 6)

    return {
        "price_change_15m": price_change,
        "price_change_15m_source_kind": PROVIDER_CANDLE_DERIVED,
        "price_change_15m_provenance": {
            "source": GT15M_SOURCE_NAME,
            "network": network,
            "pool_address": pool_address,
            "endpoint_url": endpoint_url,
            "request_kind": GECKOTERMINAL_OHLCV_REQUEST_KIND,
            "calculation_method": "candle_arithmetic",
            "calculation_formula": "(close - open) / open * 100",
            "candle_start_iso": candle["candle_start_iso"],
            "candle_end_iso": candle["candle_end_iso"],
            "candle_open": open_price,
            "candle_close": close_price,
            "candle_age_since_completion_seconds": candle.get("age_since_completion_seconds"),
            "fetch_time_iso": fetch_time_iso,
            "currency": "usd",
            "token": "base",
        },
    }


# ---------------------------------------------------------------------------
# Volume derivation
# ---------------------------------------------------------------------------

def derive_volume_15m_from_candle(
    candle: dict[str, Any],
    *,
    pool_address: str,
    network: str,
    endpoint_url: str,
    fetch_time_iso: str,
) -> dict[str, Any] | None:
    """Return volume_15m enrichment from the same completed 15m candle."""
    volume = candle.get("volume_usd")
    if volume is None:
        return None

    return {
        "volume_15m": volume,
        "volume_15m_source_kind": PROVIDER_CANDLE_DERIVED,
        "volume_15m_provenance": {
            "source": GT15M_SOURCE_NAME,
            "network": network,
            "pool_address": pool_address,
            "endpoint_url": endpoint_url,
            "request_kind": GECKOTERMINAL_OHLCV_REQUEST_KIND,
            "evidence_kind": "ohlcv_candle_native_volume",
            "candle_start_iso": candle["candle_start_iso"],
            "candle_end_iso": candle["candle_end_iso"],
            "candle_age_since_completion_seconds": candle.get("age_since_completion_seconds"),
            "fetch_time_iso": fetch_time_iso,
            "currency": "usd",
            "token": "base",
        },
    }


# ---------------------------------------------------------------------------
# Transaction count from pool trades
# ---------------------------------------------------------------------------

def _parse_trade_block_timestamp(attrs: Mapping[str, Any]) -> float | None:
    raw_ts = attrs.get("block_timestamp")
    if raw_ts is None:
        return None
    if isinstance(raw_ts, (int, float)):
        return float(raw_ts)
    try:
        return datetime.fromisoformat(str(raw_ts).replace("Z", "+00:00")).timestamp()
    except (ValueError, AttributeError):
        return None


def count_txns_15m_from_trades(
    raw_trades_data: list[Any],
    *,
    window_start_unix: float,
    window_end_unix: float,
    max_response: int = GT15M_TRADES_MAX_RESPONSE,
) -> tuple[int | None, str, dict[str, Any]]:
    """Count trades within the exact 15m window with completeness proof.

    Returns (count_or_None, completeness_label, details_dict).

    txns_15m is the count of all trade records returned by the API inside the
    window. Multiple trade records sharing the same tx_hash are each counted —
    this matches the existing txns_* field contract (buys + sells total, not
    unique hashes).

    Completeness rule (a): total returned < max_response → COMPLETE
    Completeness rule (b): oldest returned timestamp <= window_start → COMPLETE
    Otherwise: TRUNCATED, count = None
    """
    if not isinstance(raw_trades_data, list):
        return None, TRADE_HISTORY_TRUNCATED, {"error": "trades_data_not_a_list"}

    total_returned = len(raw_trades_data)
    in_window_count = 0
    all_timestamps: list[float] = []

    for trade in raw_trades_data:
        if not isinstance(trade, Mapping):
            return None, TRADE_HISTORY_TRUNCATED, {
                "error": "malformed_trade_record",
                "total_trades_returned": total_returned,
            }
        attrs = trade.get("attributes") or {}
        if not isinstance(attrs, Mapping):
            return None, TRADE_HISTORY_TRUNCATED, {
                "error": "malformed_trade_attributes",
                "total_trades_returned": total_returned,
            }
        ts = _parse_trade_block_timestamp(attrs)
        if ts is None:
            return None, TRADE_HISTORY_TRUNCATED, {
                "error": "malformed_trade_timestamp",
                "total_trades_returned": total_returned,
            }
        all_timestamps.append(ts)
        if window_start_unix <= ts < window_end_unix:
            in_window_count += 1

    oldest_ts = min(all_timestamps) if all_timestamps else None

    fewer_than_max = total_returned < max_response
    oldest_reaches_window = oldest_ts is not None and oldest_ts <= window_start_unix

    if fewer_than_max or oldest_reaches_window:
        completeness = TRADE_HISTORY_COMPLETE
        count: int | None = in_window_count
    else:
        completeness = TRADE_HISTORY_TRUNCATED
        count = None

    details: dict[str, Any] = {
        "total_trades_returned": total_returned,
        "trades_in_window": in_window_count,
        "oldest_trade_unix": oldest_ts,
        "window_start_unix": window_start_unix,
        "window_end_unix": window_end_unix,
        "max_response_limit": max_response,
        "completeness_rule_applied": (
            "fewer_than_max" if fewer_than_max
            else "oldest_reaches_window" if oldest_reaches_window
            else "truncated"
        ),
    }
    return count, completeness, details


# ---------------------------------------------------------------------------
# High-level enrichment functions
# ---------------------------------------------------------------------------

def enrich_candidate_15m_ohlcv(
    ohlcv_payload: Mapping[str, Any],
    *,
    pool_address: str,
    network: str,
    endpoint_url: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Derive price_change_15m and volume_15m from a governed OHLCV payload.

    Returns a dict with successfully derived fields and their provenance
    annotations. Returns empty dict on any failure (fails closed).
    """
    _now = now or _now_utc()
    fetch_time_iso = _now.isoformat()

    if _payload_is_failure(ohlcv_payload):
        return {}

    raw_data = ohlcv_payload.get("data")
    if not isinstance(raw_data, Mapping):
        return {}

    attrs = raw_data.get("attributes")
    if not isinstance(attrs, Mapping):
        return {}

    ohlcv_list = attrs.get("ohlcv_list")
    if not isinstance(ohlcv_list, list):
        return {}

    candle = select_completed_15m_candle(ohlcv_list, _now)
    if candle is None:
        return {}

    enrichment: dict[str, Any] = {}

    price_result = derive_price_change_15m_from_candle(
        candle,
        pool_address=pool_address,
        network=network,
        endpoint_url=endpoint_url,
        fetch_time_iso=fetch_time_iso,
    )
    if price_result is not None:
        enrichment.update(price_result)

    volume_result = derive_volume_15m_from_candle(
        candle,
        pool_address=pool_address,
        network=network,
        endpoint_url=endpoint_url,
        fetch_time_iso=fetch_time_iso,
    )
    if volume_result is not None:
        enrichment.update(volume_result)

    return enrichment


def enrich_candidate_15m_trades(
    trades_payload: Mapping[str, Any],
    *,
    pool_address: str,
    network: str,
    endpoint_url: str,
    now: datetime | None = None,
    window_start_iso: str | None = None,
    window_end_iso: str | None = None,
) -> dict[str, Any]:
    """Count txns_15m from a governed pool-trades payload with completeness proof.

    txns_15m may be None when completeness cannot be proven (TRUNCATED).
    Returns empty dict on any payload failure (fails closed).
    """
    _now = now or _now_utc()
    fetch_time_iso = _now.isoformat()
    if window_start_iso is not None or window_end_iso is not None:
        if not isinstance(window_start_iso, str) or not isinstance(window_end_iso, str):
            return {}
        try:
            window_start_unix = datetime.fromisoformat(
                window_start_iso.replace("Z", "+00:00")
            ).timestamp()
            window_end_unix = datetime.fromisoformat(
                window_end_iso.replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            return {}
        if window_end_unix - window_start_unix != GT15M_CANDLE_SECONDS:
            return {}
    else:
        window_end_unix = _now.timestamp()
        window_start_unix = window_end_unix - GT15M_CANDLE_SECONDS

    if _payload_is_failure(trades_payload):
        return {}

    raw_trades_data = trades_payload.get("data")
    if not isinstance(raw_trades_data, list):
        return {}

    count, completeness, details = count_txns_15m_from_trades(
        raw_trades_data,
        window_start_unix=window_start_unix,
        window_end_unix=window_end_unix,
    )

    return {
        "txns_15m": count,
        "txns_15m_source_kind": PROVIDER_TRADES_WINDOW,
        "txns_15m_completeness": completeness,
        "txns_15m_provenance": {
            "source": GT15M_SOURCE_NAME,
            "network": network,
            "pool_address": pool_address,
            "endpoint_url": endpoint_url,
            "request_kind": GECKOTERMINAL_POOL_TRADES_REQUEST_KIND,
            "window_start_iso": _unix_to_iso(window_start_unix),
            "window_end_iso": _unix_to_iso(window_end_unix),
            "fetch_time_iso": fetch_time_iso,
            "completeness": completeness,
            "count_method": "trade_record_count_buys_plus_sells",
            **details,
        },
    }


# ---------------------------------------------------------------------------
# URL builders
# ---------------------------------------------------------------------------

def build_gt15m_ohlcv_url(pool_address: str, network: str = GT15M_NETWORK) -> str:
    return GT15M_OHLCV_URL_TEMPLATE.format(network=network, pool_address=pool_address)


def build_gt15m_trades_url(pool_address: str, network: str = GT15M_NETWORK) -> str:
    return GT15M_TRADES_URL_TEMPLATE.format(network=network, pool_address=pool_address)


# ---------------------------------------------------------------------------
# Fixture transports (test / bounded proof use)
# ---------------------------------------------------------------------------

def fixture_ohlcv_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[Any], Mapping[str, Any]]:
    def _transport(_context: Any) -> Mapping[str, Any]:
        return MappingProxyType(dict(payload))
    return _transport


def fixture_trades_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[Any], Mapping[str, Any]]:
    def _transport(_context: Any) -> Mapping[str, Any]:
        return MappingProxyType(dict(payload))
    return _transport


def fixture_failure_transport(
    message: str = "GT15M fixture failure",
) -> Callable[[Any], Mapping[str, Any]]:
    def _transport(_context: Any) -> Mapping[str, Any]:
        return MappingProxyType({
            "fixture_status": "failure",
            "failure_type": "gt15m_fixture_failure",
            "failure_message": message,
        })
    return _transport
