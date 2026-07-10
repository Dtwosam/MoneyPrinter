"""Governed PumpPortal free-stream discovery adapter.

Supports only the two allowed free public streams:
  - pumpfun_launch_stream  (subscribeNewToken events)
  - pumpfun_migration_stream  (subscribeMigration events)

Metered, paid, or trading-related streams such as subscribeTokenTrade
and subscribeAccountTrade are outside the allowed_request_kinds and
are rejected at the Source Governor boundary.

No persistent streaming loop is started here. Controlled collection is
bounded and operator-approved. Live transport requires the 'websockets'
package which is not included in project dependencies by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceAdapterContract,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)


PUMPPORTAL_SOURCE_NAME = "pumpportal"

ALLOWED_REQUEST_KINDS = frozenset({
    "pumpfun_launch_stream",
    "pumpfun_migration_stream",
})

_SOLANA_CHAIN = "solana"


@dataclass(frozen=True)
class PumpPortalAdapterMetadata:
    source_name: str = PUMPPORTAL_SOURCE_NAME
    display_name: str = "PumpPortal"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = True
    fixture_transport_only: bool = False


class PumpPortalAdapter:
    """PumpPortal adapter shell, disabled unless a governed caller injects transport.

    Only free launch and migration stream data is accepted. No metered
    streams, no trading endpoints, no transaction building, no swaps.
    """

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = PumpPortalAdapterMetadata()
        self.contract = build_pumpportal_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("PumpPortal adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("PumpPortal adapter requires an explicit transport")
        _validate_context(context, PUMPPORTAL_SOURCE_NAME, self.contract)

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return _failure_result(
                context.request.request_kind, "pumpportal_transport_error", str(exc)
            )
        return normalize_pumpportal_payload(payload, request_kind=context.request.request_kind)


def build_pumpportal_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(PUMPPORTAL_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("PumpPortal contract violates Source Governor boundary")
    return contract


def build_pumpportal_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> PumpPortalAdapter:
    return PumpPortalAdapter(enabled=enabled, fixture_transport=fixture_transport)


def fixture_success_transport(
    payload: Mapping[str, Any],
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_failure_transport(
    message: str = "PumpPortal fixture failure",
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(
            {
                "fixture_status": "failure",
                "failure_type": "pumpportal_fixture_failure",
                "failure_message": message,
            }
        )

    return transport


_PUMPPORTAL_WS_URL = "wss://pumpportal.fun/api/data"
_PUMPPORTAL_SUBSCRIBE_NEW_TOKEN = {"method": "subscribeNewToken"}
_PUMPPORTAL_MAX_EVENTS_DEFAULT = 5
_PUMPPORTAL_DURATION_SECONDS_DEFAULT = 30.0
_PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT = 10.0


def build_pumpportal_live_transport(
    *,
    max_events: int = _PUMPPORTAL_MAX_EVENTS_DEFAULT,
    duration_seconds: float = _PUMPPORTAL_DURATION_SECONDS_DEFAULT,
    connect_timeout_seconds: float = _PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Returns a bounded live transport for pumpfun_launch_stream.

    Requires the 'websockets' package (declared in project dependencies).
    Raises RuntimeError at build time if websockets cannot be imported.

    Bounds: max_events events or duration_seconds wall clock (whichever comes
    first). connect_timeout_seconds caps the initial WebSocket handshake.
    Zero reconnects. No background threads. No scheduler jobs. No DB writes.

    Raises ValueError if any bound exceeds the approved maximum.
    """
    if max_events > _PUMPPORTAL_MAX_EVENTS_DEFAULT:
        raise ValueError(
            f"max_events {max_events} exceeds approved limit of {_PUMPPORTAL_MAX_EVENTS_DEFAULT}"
        )
    if duration_seconds > _PUMPPORTAL_DURATION_SECONDS_DEFAULT:
        raise ValueError(
            f"duration_seconds {duration_seconds} exceeds approved limit of "
            f"{_PUMPPORTAL_DURATION_SECONDS_DEFAULT}"
        )
    if connect_timeout_seconds > _PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT:
        raise ValueError(
            f"connect_timeout_seconds {connect_timeout_seconds} exceeds approved limit of "
            f"{_PUMPPORTAL_CONNECT_TIMEOUT_DEFAULT}"
        )
    try:
        import websockets as _ws
    except ImportError as exc:
        raise RuntimeError(
            "build_pumpportal_live_transport requires the 'websockets' package; "
            "add websockets to project dependencies before using live transport"
        ) from exc

    import asyncio
    import json

    _url = _PUMPPORTAL_WS_URL
    _subscribe_msg = json.dumps(_PUMPPORTAL_SUBSCRIBE_NEW_TOKEN)
    _max_ev = max_events
    _duration = duration_seconds
    _connect_timeout = connect_timeout_seconds

    async def _collect() -> list[dict]:
        events: list[dict] = []
        try:
            async with asyncio.timeout(_connect_timeout):
                ws = await _ws.connect(_url)
        except Exception:
            return events
        try:
            await ws.send(_subscribe_msg)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + _duration
            while len(events) < _max_ev:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    async with asyncio.timeout(remaining):
                        raw = await ws.recv()
                    try:
                        data = json.loads(raw)
                    except (ValueError, TypeError):
                        continue
                    if isinstance(data, dict):
                        events.append(data)
                except asyncio.TimeoutError:
                    break
        finally:
            try:
                await ws.close()
            except Exception:
                pass
        return events

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        collected = asyncio.run(_collect())
        return MappingProxyType(
            {
                "events": collected,
                "subscription_method": "subscribeNewToken",
            }
        )

    return transport


def normalize_pumpportal_payload(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
) -> NormalizedSourceResult:
    if request_kind not in ALLOWED_REQUEST_KINDS:
        return _failure_result(
            request_kind,
            "pumpportal_request_kind_not_allowed",
            "PumpPortal request kind is not allowed",
        )

    fixture_status = payload.get("fixture_status")
    if fixture_status == "failure":
        return _failure_result(
            request_kind,
            str(payload.get("failure_type") or "pumpportal_fixture_failure"),
            str(payload.get("failure_message") or "PumpPortal fixture failure"),
        )
    if fixture_status == "stale":
        return NormalizedSourceResult(
            source_name=PUMPPORTAL_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="pumpportal_stale_data",
            failure_message="PumpPortal fixture stale data",
        )

    # Accept pre-normalized "tokens" list (matches existing pumpportal_payload fixture format)
    # or raw "events" list (batch of PumpPortal stream events)
    pre_normalized = payload.get("tokens")
    if isinstance(pre_normalized, list):
        solana_tokens = [
            t for t in pre_normalized
            if isinstance(t, Mapping) and str(t.get("chain") or "").lower() == _SOLANA_CHAIN
        ]
    else:
        raw_events = payload.get("events") or []
        if not isinstance(raw_events, list):
            return _failure_result(
                request_kind,
                "pumpportal_missing_event_list",
                "PumpPortal payload missing tokens or events list",
            )
        solana_tokens = []
        for event in raw_events:
            if not isinstance(event, Mapping):
                continue
            normalized = _normalize_pumpportal_event(event, request_kind)
            if normalized:
                solana_tokens.append(normalized)

    if not solana_tokens:
        return _failure_result(
            request_kind,
            "pumpportal_no_valid_solana_events",
            "PumpPortal payload contained no valid Solana events",
        )

    stale = bool(payload.get("fixture_stale"))
    return NormalizedSourceResult(
        source_name=PUMPPORTAL_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": PUMPPORTAL_SOURCE_NAME,
                "request_kind": request_kind,
                "tokens": solana_tokens,
            }
        ),
        status_code=200,
    )


_PUMPPORTAL_LAUNCH_STALENESS_THRESHOLD_SECONDS = 3600.0


def _parse_event_ts(value: Any) -> datetime | None:
    """Parse a PumpPortal event timestamp field to UTC datetime, or None if invalid."""
    if value is None or value == "" or value == 0:
        return None
    if isinstance(value, (int, float)):
        try:
            f = float(value)
            if f <= 0:
                return None
            epoch_s = f / 1000.0 if f > 1e10 else f
            return datetime.fromtimestamp(epoch_s, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def _extract_launch_timestamp(
    event: Mapping[str, Any],
    observation_iso: str,
) -> str | None:
    """Extract and validate token creation timestamp from a pumpfun_launch_stream event.

    Priority: tokenCreatedAt → createdTimestamp → timestamp (first non-empty wins).
    Returns ISO-8601 UTC string if valid; None otherwise.

    Rejects: missing, zero, negative, unparseable, future relative to observation,
    or stale (older than _PUMPPORTAL_LAUNCH_STALENESS_THRESHOLD_SECONDS).
    Must NOT be called for migration events.
    """
    raw = None
    for key in ("tokenCreatedAt", "createdTimestamp", "timestamp"):
        v = event.get(key)
        if v is not None and v != "" and v != 0:
            raw = v
            break
    if raw is None:
        return None

    obs_dt = _parse_event_ts(observation_iso)
    if obs_dt is None:
        obs_dt = datetime.now(timezone.utc)

    event_dt = _parse_event_ts(raw)
    if event_dt is None:
        return None

    if event_dt > obs_dt:
        return None

    staleness = (obs_dt - event_dt).total_seconds()
    if staleness > _PUMPPORTAL_LAUNCH_STALENESS_THRESHOLD_SECONDS:
        return None

    return event_dt.isoformat()


def _normalize_pumpportal_event(
    event: Mapping[str, Any],
    request_kind: str,
) -> dict[str, Any] | None:
    """Normalize one raw PumpPortal stream event into the discovery pipeline format."""
    token_mint = event.get("mint") or event.get("tokenMint") or event.get("token_mint")
    if not token_mint:
        return None

    # For migration events, prefer the post-migration pool address
    pair_address = (
        event.get("newRaydiumPool")
        or event.get("pairAddress")
        or event.get("pair_address")
        or event.get("bondingCurveKey")
    )

    # Estimate liquidity from bonding curve SOL reserves if available
    liquidity_usd = _to_float(
        event.get("liquidity_usd")
        or event.get("liquidityUsd")
        or _sol_to_approx_usd(event.get("vSolInBondingCurve") or event.get("solAmount"))
    )

    # T2 token-age evidence: launch events only.
    # Observation ref for staleness uses explicit captured_at; falls back to current time.
    # Migration events never provide token_created_at.
    token_created_at: str | None = None
    live_observed_launch: bool = False
    if request_kind == "pumpfun_launch_stream":
        _observation_ref = event.get("captured_at") or _current_iso()
        token_created_at = _extract_launch_timestamp(event, _observation_ref)
        # OBSERVED_LIVE_LAUNCH only when no explicit timestamp field exists at all.
        # A stale, invalid, or zero timestamp still counts as "field present" —
        # only complete absence of all three fields triggers this flag.
        if token_created_at is None and not any(
            k in event for k in ("tokenCreatedAt", "createdTimestamp", "timestamp")
        ):
            live_observed_launch = True

    return {
        "chain": _SOLANA_CHAIN,
        "mint": token_mint,
        "pairAddress": pair_address,
        "request_kind": request_kind,
        "symbol": event.get("symbol"),
        "name": event.get("name"),
        "dex": "pumpfun" if request_kind == "pumpfun_launch_stream" else "raydium",
        "poolSource": PUMPPORTAL_SOURCE_NAME,
        "price_usd": _to_str_or_none(
            event.get("priceUsd") or event.get("price_usd")
        ),
        "liquidity_usd": liquidity_usd,
        "captured_at": _current_iso() if not event.get("captured_at") and not event.get("timestamp") else (
            event.get("captured_at") or event.get("timestamp")
        ),
        "token_created_at": token_created_at,
        "live_observed_launch": live_observed_launch,
    }


def _sol_to_approx_usd(sol_amount: Any) -> float | None:
    """Approximate SOL amount to USD using a conservative fixed rate for gate comparison only."""
    amount = _to_float(sol_amount)
    if amount is None:
        return None
    return amount * 150.0


def _to_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_str_or_none(value: Any) -> str | None:
    if value is None or value == "":
        return None
    return str(value)


def _current_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _validate_context(
    context: SourceAdapterContext,
    source_name: str,
    contract: SourceAdapterContract,
) -> None:
    if not context or not context.governor_approved:
        raise PermissionError("source adapter execution requires Source Governor approval")
    if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
        raise PermissionError("source adapter execution requires governed recording path")
    if context.request.source_name != source_name:
        raise ValueError("source request does not match adapter")
    if context.request.request_kind not in contract.allowed_request_kinds:
        raise ValueError("source request kind is not allowed for adapter")


def _failure_result(
    request_kind: str,
    failure_type: str,
    failure_message: str,
) -> NormalizedSourceResult:
    return NormalizedSourceResult(
        source_name=PUMPPORTAL_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.FAILED,
        data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
        failure_type=failure_type,
        failure_message=failure_message,
    )
