"""Disabled-by-default DexScreener source adapter boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence
from urllib import error as url_error
from urllib import request as url_request

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.sources.contracts import (
    GOVERNOR_ONLY_EXECUTION_PATH,
    NormalizedSourceResult,
    SourceAdapterContext,
    SourceAdapterContract,
    build_source_adapter_contract,
    validate_source_adapter_contract,
)
from printer_v1.sources.operational_source_contracts import (
    DEXSCREENER_EXACT_PAIR_URL,
    DEXSCREENER_PROFILES_URL,
    DEXSCREENER_TOKEN_BATCH_URL,
)


DEXSCREENER_SOURCE_NAME = "dexscreener"

# Solana infrastructure / native-quote mints. A DexScreener pair whose
# baseToken.address resolves to one of these is an infrastructure/quote asset
# (WSOL / USDC / USDT), never a memecoin discovery target. These must be
# excluded before a candidate is emitted so an infrastructure mint can never
# occupy a memecoin tracking slot. This mirrors
# geckoterminal._SOLANA_NATIVE_QUOTE_MINTS exactly. Source of truth:
# docs/solana-builder-source-of-truth/solana-mint-addresses.md
_SOLANA_INFRASTRUCTURE_MINTS = frozenset({
    "So11111111111111111111111111111111111111112",   # WSOL (Wrapped SOL / native SOL)
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC (Circle official Solana mainnet)
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT / USDt (Tether Solana)
})

DEXSCREENER_SMOKE_URL = "https://api.dexscreener.com/latest/dex/search?q=SOL"
DEXSCREENER_PAIR_URL_TEMPLATE = DEXSCREENER_EXACT_PAIR_URL
DEXSCREENER_TOKEN_URL_TEMPLATE = "https://api.dexscreener.com/latest/dex/tokens/{token_mint}"
# Fresh-listing discovery vector (keyless, free — verified 2026-07-12):
#   1. /token-profiles/latest/v1  -> recently profiled tokens (chainId, tokenAddress)
#   2. /tokens/v1/solana/{addrs}  -> pair data for up to 30 comma-joined mints
# token-profiles is documented at 60 req/min. This surfaces freshly listed
# Solana memecoins rather than the popular-token repeats returned by search.
DEXSCREENER_TOKEN_PROFILES_URL = DEXSCREENER_PROFILES_URL
DEXSCREENER_TOKENS_BATCH_URL_TEMPLATE = DEXSCREENER_TOKEN_BATCH_URL
_DEXSCREENER_FRESH_PROFILES_MAX_TOKENS = 30
DEXSCREENER_SMOKE_TIMEOUT_SECONDS = 5.0
DEXSCREENER_PAIR_PROVIDER_RATE_LIMIT_PER_MINUTE = 300
DEXSCREENER_TRANSPORT_OPERATION_COST = 1
DEXSCREENER_PUBLIC_API_HEADERS = {
    "User-Agent": "PrinterV1/0.1 (+paper-only source check)",
    "Accept": "application/json",
}


@dataclass(frozen=True)
class DexScreenerAdapterMetadata:
    source_name: str = DEXSCREENER_SOURCE_NAME
    display_name: str = "DexScreener"
    enabled_by_default: bool = False
    requires_governor_context: bool = True
    supports_network_execution: bool = False
    fixture_transport_only: bool = True


class DexScreenerAdapter:
    """DexScreener adapter shell, disabled unless an operator path enables it."""

    def __init__(
        self,
        *,
        enabled: bool = False,
        fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
        smoke_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    ) -> None:
        self.metadata = DexScreenerAdapterMetadata()
        self.contract = build_dexscreener_adapter_contract()
        self.enabled = enabled
        self.transport = fixture_transport or smoke_transport
        self.call_count = 0

    def execute(self, context: SourceAdapterContext) -> NormalizedSourceResult:
        if not self.enabled:
            raise PermissionError("DexScreener adapter is disabled by default")
        if self.transport is None:
            raise PermissionError("DexScreener adapter requires an explicit transport")
        if not context or not context.governor_approved:
            raise PermissionError("DexScreener adapter execution requires Source Governor approval")
        if context.execution_path != GOVERNOR_ONLY_EXECUTION_PATH:
            raise PermissionError("DexScreener adapter execution requires governed recording path")
        if context.request.source_name != DEXSCREENER_SOURCE_NAME:
            raise ValueError("source request does not match DexScreener")
        if context.request.request_kind not in self.contract.allowed_request_kinds:
            raise ValueError("source request kind is not allowed for DexScreener")

        self.call_count += 1
        try:
            payload = self.transport(context)
        except Exception as exc:
            return NormalizedSourceResult(
                source_name=DEXSCREENER_SOURCE_NAME,
                request_kind=context.request.request_kind,
                source_status=SourceStatus.FAILED,
                data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
                failure_type="dexscreener_transport_error",
                failure_message=str(exc),
            )
        return normalize_dexscreener_fixture_result(payload, request_kind=context.request.request_kind)


def build_dexscreener_adapter_contract() -> SourceAdapterContract:
    contract = build_source_adapter_contract(DEXSCREENER_SOURCE_NAME)
    if not validate_source_adapter_contract(contract):
        raise ValueError("DexScreener contract violates Source Governor boundary")
    return contract


def get_dexscreener_adapter_metadata() -> DexScreenerAdapterMetadata:
    return DexScreenerAdapterMetadata()


def build_dexscreener_adapter(
    *,
    enabled: bool = False,
    fixture_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
    smoke_transport: Callable[[SourceAdapterContext], Mapping[str, Any]] | None = None,
) -> DexScreenerAdapter:
    return DexScreenerAdapter(
        enabled=enabled,
        fixture_transport=fixture_transport,
        smoke_transport=smoke_transport,
    )


def fixture_success_transport(payload: Mapping[str, Any]) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType(dict(payload))

    return transport


def fixture_rate_limited_transport() -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        return MappingProxyType({"fixture_status": "rate_limited", "retry_after_seconds": 60})

    return transport


def build_dexscreener_smoke_transport(
    *,
    timeout_seconds: float = DEXSCREENER_SMOKE_TIMEOUT_SECONDS,
    endpoint: str = DEXSCREENER_SMOKE_URL,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        from printer_v1.sources.measured_transport import (
            build_transport_identity,
            enforce_normalized_row_ceiling,
            measured_payload_fields,
        )

        def _pair_identity(
            result: str, *, response_bytes: int = 0, normalized_rows: int = 0
        ) -> Any:
            # One outbound GET == exactly one measured transport identity,
            # emitted on every outcome class (success, byte/row ceiling,
            # malformed body, HTTP error, rate limit, decode failure, timeout).
            return build_transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source_name="dexscreener_pair",
                endpoint_owner="dexscreener",
                governed_request_kind="dexscreener_pair_snapshot",
                method_or_endpoint=f"GET {endpoint}",
                within_request_ordinal=1,
                target_category="exact_pair",
                response_bytes=int(response_bytes),
                normalized_rows=int(normalized_rows),
                result=result,
            )

        def _measured(payload: dict, identity: Any) -> Mapping[str, Any]:
            payload.update(measured_payload_fields([identity]))
            return MappingProxyType(payload)

        request = url_request.Request(
            endpoint,
            headers=DEXSCREENER_PUBLIC_API_HEADERS,
            method="GET",
        )
        try:
            with url_request.urlopen(request, timeout=timeout_seconds) as response:
                raw_body = response.read(512_001)
                response_bytes = len(raw_body)
                if response_bytes > 512_000:
                    return _measured(
                        {
                            "fixture_status": "failure",
                            "failure_type": "dexscreener_pair_byte_ceiling",
                            "failure_message": "DexScreener pair response exceeded byte ceiling",
                            "response_bytes": response_bytes,
                        },
                        _pair_identity("BYTE_CEILING", response_bytes=response_bytes),
                    )
                payload = json.loads(raw_body.decode("utf-8"))
                if isinstance(payload, dict):
                    pairs = payload.get("pairs")
                    pair_count = len(pairs) if isinstance(pairs, list) else 0
                    try:
                        enforce_normalized_row_ceiling(
                            "dexscreener_exact_pair_rows", pair_count
                        )
                    except Exception as exc:  # MeasuredTransportError
                        return _measured(
                            {
                                "fixture_status": "failure",
                                "failure_type": "dexscreener_exact_pair_row_ceiling",
                                "failure_message": str(exc),
                                "response_bytes": response_bytes,
                            },
                            _pair_identity(
                                "ROW_CEILING",
                                response_bytes=response_bytes,
                                normalized_rows=pair_count,
                            ),
                        )
                    payload = dict(payload)
                    payload["_source_status_code"] = getattr(response, "status", None)
                    return _measured(
                        payload,
                        _pair_identity(
                            "OK",
                            response_bytes=response_bytes,
                            normalized_rows=pair_count,
                        ),
                    )
                # A non-object body is a payload/schema defect, not a transport
                # failure: it must never trigger the V2-9.5 fallback.
                return _measured(
                    {
                        "fixture_status": "failure",
                        "failure_type": "dexscreener_malformed_payload",
                        "failure_message": "DexScreener returned non-object payload",
                        "response_bytes": response_bytes,
                    },
                    _pair_identity("MALFORMED", response_bytes=response_bytes),
                )
        except url_error.HTTPError as exc:
            # V2-9.5 eligibility split: 429 and temporary 5xx are transient and
            # fallback-eligible; 4xx is a deterministic client error and is not.
            if exc.code == 429:
                return _measured(
                    {"fixture_status": "rate_limited", "retry_after_seconds": 60},
                    _pair_identity("RATE_LIMITED"),
                )
            if 500 <= int(exc.code) <= 599:
                return _measured(
                    {
                        "fixture_status": "failure",
                        "failure_type": "dexscreener_http_server_error",
                        "failure_message": f"DexScreener HTTP error {exc.code}",
                    },
                    _pair_identity("HTTP_SERVER_ERROR"),
                )
            return _measured(
                {
                    "fixture_status": "failure",
                    "failure_type": "dexscreener_http_client_error",
                    "failure_message": f"DexScreener HTTP error {exc.code}",
                },
                _pair_identity("HTTP_CLIENT_ERROR"),
            )
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            # Parser/decode defect — a payload problem, never fallback-eligible.
            return _measured(
                {
                    "fixture_status": "failure",
                    "failure_type": "dexscreener_malformed_payload",
                    "failure_message": str(exc),
                },
                _pair_identity("DECODE_FAILURE"),
            )
        except (OSError, TimeoutError) as exc:
            # TLS/connection interruption or connect/read timeout. ssl.SSLError
            # (e.g. SSLV3_ALERT_BAD_RECORD_MAC) is an OSError subclass and is
            # caught here. Transient and fallback-eligible.
            return _measured(
                {
                    "fixture_status": "failure",
                    "failure_type": "dexscreener_transport_failure",
                    "failure_message": str(exc),
                },
                _pair_identity("TRANSPORT_FAILURE"),
            )

    return transport


def build_dexscreener_token_transport(
    token_mint: str,
    *,
    timeout_seconds: float = DEXSCREENER_SMOKE_TIMEOUT_SECONDS,
    endpoint_template: str = DEXSCREENER_TOKEN_URL_TEMPLATE,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Build a real transport callable for a specific token mint address.

    Uses the free/public DexScreener tokens endpoint, not the generic SOL search.
    No authentication. No paid tier. Suitable for E2I one-shot governed smoke.
    """
    endpoint = endpoint_template.format(token_mint=token_mint)
    return build_dexscreener_smoke_transport(
        timeout_seconds=timeout_seconds,
        endpoint=endpoint,
    )


def build_dexscreener_pair_snapshot_transport(
    pair_address: str,
    *,
    timeout_seconds: float = DEXSCREENER_SMOKE_TIMEOUT_SECONDS,
    endpoint_template: str = DEXSCREENER_PAIR_URL_TEMPLATE,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    endpoint = endpoint_template.format(pair_address=pair_address)
    return build_dexscreener_smoke_transport(
        timeout_seconds=timeout_seconds,
        endpoint=endpoint,
    )


def _dexscreener_http_get_json(
    endpoint: str,
    timeout_seconds: float,
    *,
    byte_ceiling: int = 2_000_000,
) -> tuple[Any, int]:
    """GET one DexScreener endpoint and return (parsed JSON, response_bytes).

    Raises url_error.HTTPError / OSError / json.JSONDecodeError / MeasuredTransportError
    on failure so the caller can map to the correct fixture_status. No auth, no API key.
    """
    from printer_v1.sources.measured_transport import MeasuredTransportError

    request = url_request.Request(endpoint, headers=DEXSCREENER_PUBLIC_API_HEADERS, method="GET")
    with url_request.urlopen(request, timeout=timeout_seconds) as response:
        raw_body = response.read(int(byte_ceiling) + 1)
        response_bytes = len(raw_body)
        if response_bytes > int(byte_ceiling):
            raise MeasuredTransportError(
                f"SOURCE_RESPONSE_BYTE_CEILING:dexscreener:{byte_ceiling}"
            )
        return json.loads(raw_body.decode("utf-8")), response_bytes


def build_dexscreener_fresh_profiles_transport(
    *,
    timeout_seconds: float = DEXSCREENER_SMOKE_TIMEOUT_SECONDS,
    max_tokens: int = _DEXSCREENER_FRESH_PROFILES_MAX_TOKENS,
    profiles_endpoint: str = DEXSCREENER_TOKEN_PROFILES_URL,
    tokens_endpoint_template: str = DEXSCREENER_TOKENS_BATCH_URL_TEMPLATE,
) -> Callable[[SourceAdapterContext], Mapping[str, Any]]:
    """Governed fresh-listing discovery transport for Solana memecoins.

    Two keyless GETs inside one governed request/response:
      1. latest token profiles -> distinct Solana token mints (recency-ordered),
      2. one batch token-pairs lookup -> pair data for those mints.

    Returns a `{"pairs": [...]}` payload consumed by
    normalize_dexscreener_fixture_result, which applies the Solana-only and
    infrastructure-mint exclusion filters. Recency is a categorical intake fact;
    no boost amount, ordering position, or any numeric is used as a score.
    """
    cap = max(1, min(int(max_tokens), _DEXSCREENER_FRESH_PROFILES_MAX_TOKENS))

    def transport(context: SourceAdapterContext) -> Mapping[str, Any]:
        del context
        from printer_v1.sources.measured_transport import (
            BYTE_CEILINGS,
            MeasuredTransportError,
            ROW_CEILINGS,
            build_transport_identity,
            enforce_normalized_row_ceiling,
            measured_payload_fields,
        )

        identities = []
        profiles_bytes = 0
        pairs_bytes = 0

        def _fail(
            *,
            failure_type: str,
            failure_message: str,
            fixture_status: str = "failure",
            extra: dict | None = None,
            step1_result: str = "FAILED",
            step1_rows: int = 0,
            step1_bytes: int = 0,
            include_step1: bool = True,
            step2: bool = False,
            step2_result: str = "FAILED",
            step2_rows: int = 0,
            step2_bytes: int = 0,
        ) -> MappingProxyType:
            local = list(identities)
            if include_step1 and not local:
                local.append(
                    build_transport_identity(
                        stage="DEXSCREENER_DISCOVERY",
                        source_name="dexscreener_profiles",
                        endpoint_owner="dexscreener",
                        governed_request_kind="dexscreener_fresh_profiles",
                        method_or_endpoint="GET /token-profiles/latest/v1",
                        within_request_ordinal=1,
                        target_category="fresh_profiles",
                        response_bytes=int(step1_bytes),
                        normalized_rows=int(step1_rows),
                        result=step1_result,
                    )
                )
            if step2:
                local.append(
                    build_transport_identity(
                        stage="DEXSCREENER_DISCOVERY",
                        source_name="dexscreener_pair",
                        endpoint_owner="dexscreener",
                        governed_request_kind="dexscreener_fresh_profiles",
                        method_or_endpoint="GET /tokens/v1/solana/{mints}",
                        within_request_ordinal=2,
                        target_category="token_pairs",
                        response_bytes=int(step2_bytes),
                        normalized_rows=int(step2_rows),
                        result=step2_result,
                    )
                )
            payload: dict = {
                "fixture_status": fixture_status,
                "failure_type": failure_type,
                "failure_message": failure_message,
            }
            if extra:
                payload.update(extra)
            if fixture_status == "rate_limited":
                payload.setdefault("retry_after_seconds", 60)
            payload.update(measured_payload_fields(local))
            return MappingProxyType(payload)

        # Step 1 — latest profiles.
        try:
            profiles, profiles_bytes = _dexscreener_http_get_json(
                profiles_endpoint,
                timeout_seconds,
                byte_ceiling=int(BYTE_CEILINGS.get("dexscreener_profiles", 2_000_000)),
            )
        except MeasuredTransportError as exc:
            return _fail(
                failure_type="dexscreener_profiles_byte_ceiling",
                failure_message=str(exc),
                step1_bytes=profiles_bytes,
            )
        except url_error.HTTPError as exc:
            if exc.code == 429:
                return _fail(
                    failure_type="dexscreener_profiles_rate_limited",
                    failure_message="DexScreener profiles rate limited",
                    fixture_status="rate_limited",
                    extra={"retry_after_seconds": 60},
                )
            return _fail(
                failure_type="dexscreener_profiles_http_error",
                failure_message=f"DexScreener profiles HTTP error {exc.code}",
            )
        except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _fail(
                failure_type="dexscreener_profiles_transport_failure",
                failure_message=str(exc),
            )

        if not isinstance(profiles, list):
            return _fail(
                failure_type="dexscreener_profiles_malformed",
                failure_message="DexScreener token-profiles did not return a list",
                step1_bytes=profiles_bytes,
            )

        seen: set[str] = set()
        solana_addrs: list[str] = []
        for entry in profiles:
            if not isinstance(entry, Mapping) or entry.get("chainId") != "solana":
                continue
            addr = entry.get("tokenAddress")
            if isinstance(addr, str) and addr and addr not in seen:
                seen.add(addr)
                solana_addrs.append(addr)
            if len(solana_addrs) >= cap:
                break

        try:
            enforce_normalized_row_ceiling(
                "dexscreener_fresh_profile_mints", len(solana_addrs)
            )
        except MeasuredTransportError as exc:
            return _fail(
                failure_type="dexscreener_fresh_profile_row_ceiling",
                failure_message=str(exc),
                step1_bytes=profiles_bytes,
                step1_rows=len(solana_addrs),
            )

        identities.append(
            build_transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source_name="dexscreener_profiles",
                endpoint_owner="dexscreener",
                governed_request_kind="dexscreener_fresh_profiles",
                method_or_endpoint="GET /token-profiles/latest/v1",
                within_request_ordinal=1,
                target_category="fresh_profiles",
                response_bytes=profiles_bytes,
                normalized_rows=len(solana_addrs),
                result="OK",
            )
        )

        if not solana_addrs:
            return _fail(
                failure_type="dexscreener_no_solana_profiles",
                failure_message="DexScreener latest profiles contained no Solana tokens",
                include_step1=False,  # already in identities
                step1_bytes=profiles_bytes,
            )

        # Step 2 — batch pair lookup for the fresh Solana mints.
        endpoint = tokens_endpoint_template.format(addresses=",".join(solana_addrs))
        try:
            pairs, pairs_bytes = _dexscreener_http_get_json(
                endpoint,
                timeout_seconds,
                byte_ceiling=int(BYTE_CEILINGS.get("dexscreener_pair", 512_000)),
            )
        except MeasuredTransportError as exc:
            return _fail(
                failure_type="dexscreener_tokens_byte_ceiling",
                failure_message=str(exc),
                include_step1=False,
                step2=True,
                step2_bytes=pairs_bytes,
            )
        except url_error.HTTPError as exc:
            if exc.code == 429:
                return _fail(
                    failure_type="dexscreener_tokens_rate_limited",
                    failure_message="DexScreener tokens rate limited",
                    fixture_status="rate_limited",
                    extra={"retry_after_seconds": 60},
                    include_step1=False,
                    step2=True,
                )
            return _fail(
                failure_type="dexscreener_tokens_http_error",
                failure_message=f"DexScreener tokens HTTP error {exc.code}",
                include_step1=False,
                step2=True,
            )
        except (OSError, TimeoutError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            return _fail(
                failure_type="dexscreener_tokens_transport_failure",
                failure_message=str(exc),
                include_step1=False,
                step2=True,
            )

        if not isinstance(pairs, list):
            return _fail(
                failure_type="dexscreener_tokens_malformed",
                failure_message="DexScreener tokens batch did not return a list",
                include_step1=False,
                step2=True,
                step2_bytes=pairs_bytes,
            )

        try:
            # Provider-controlled multi-row pair arrays fail closed above ceiling.
            enforce_normalized_row_ceiling(
                "dexscreener_exact_pair_rows",
                len(pairs),
                declared={
                    **dict(ROW_CEILINGS),
                    # Fresh-profile batch may return many pairs; use profile mint
                    # ceiling * small fan-out bound, not the exact-pair snapshot.
                    "dexscreener_exact_pair_rows": int(
                        ROW_CEILINGS["dexscreener_fresh_profile_mints"]
                    )
                    * 4,
                },
            )
        except MeasuredTransportError as exc:
            return _fail(
                failure_type="dexscreener_pair_row_ceiling",
                failure_message=str(exc),
                include_step1=False,
                step2=True,
                step2_bytes=pairs_bytes,
                step2_rows=len(pairs),
            )

        identities.append(
            build_transport_identity(
                stage="DEXSCREENER_DISCOVERY",
                source_name="dexscreener_pair",
                endpoint_owner="dexscreener",
                governed_request_kind="dexscreener_fresh_profiles",
                method_or_endpoint="GET /tokens/v1/solana/{mints}",
                within_request_ordinal=2,
                target_category="token_pairs",
                response_bytes=pairs_bytes,
                normalized_rows=len(pairs),
                result="OK",
            )
        )
        payload = {
            "pairs": pairs,
            "_source_status_code": 200,
            "_fresh_profiles_solana_count": len(solana_addrs),
        }
        payload.update(measured_payload_fields(identities))
        return MappingProxyType(payload)

    return transport


def _pairs_field_type_label(pairs: Any, *, present: bool) -> str:
    """Stable categorical label for a DexScreener ``pairs`` field shape."""
    if not present:
        return "MISSING"
    if pairs is None:
        return "NULL"
    if isinstance(pairs, list):
        return "LIST"
    if isinstance(pairs, dict):
        return "OBJECT"
    if isinstance(pairs, bool):
        # bool is a subclass of int; classify before NUMBER.
        return "BOOLEAN"
    if isinstance(pairs, str):
        return "STRING"
    if isinstance(pairs, (int, float)):
        return "NUMBER"
    return "OTHER"


def _is_exact_pair_request_kind(request_kind: str) -> bool:
    """True only for exact-pair snapshot request kinds (not search/fresh-profile)."""
    rk = str(request_kind or "").casefold()
    if not rk:
        return False
    if "fresh" in rk or "profile" in rk or "search" in rk or "token_discovery" in rk:
        return False
    if rk in {"pair_market_snapshot", "dexscreener_pair_snapshot"}:
        return True
    if rk.endswith("_pair_snapshot"):
        return True
    return "pair_market" in rk or ("pair" in rk and "snapshot" in rk)


def _exact_pair_success_envelope(payload: Mapping[str, Any]) -> bool:
    """Pinned successful exact-pair envelope under the DexScreener contract.

    Contract envelope is ``{schemaVersion, pairs}``. Live exact-pair no-match
    responses may also arrive as HTTP 200 measured transports without raising a
    fixture failure. Either marker is accepted; fixture failures are not.
    """
    if payload.get("fixture_status") in {"failure", "rate_limited"}:
        return False
    schema = payload.get("schemaVersion")
    if isinstance(schema, str) and schema.strip():
        return True
    http_status = payload.get("_source_status_code")
    if http_status is None:
        http_status = payload.get("source_http_status")
    if http_status is None:
        http_status = payload.get("status_code")
    try:
        return int(http_status) == 200
    except (TypeError, ValueError):
        return False


def _dexscreener_pairs_schema_diagnostics(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
    measured_payload: Mapping[str, Any],
) -> dict[str, Any]:
    """Bounded schema diagnostics for missing/non-list ``pairs`` (no raw body)."""
    present = "pairs" in payload
    pairs = payload.get("pairs") if present else None
    http_status = payload.get("_source_status_code")
    if http_status is None:
        http_status = payload.get("source_http_status")
    if http_status is None:
        http_status = payload.get("status_code")
    diagnostics = {
        **dict(measured_payload),
        "pairs_field_present": bool(present),
        "pairs_field_type": _pairs_field_type_label(pairs, present=present),
        "pairs_count": None,
        "request_kind": str(request_kind),
    }
    if http_status is not None:
        try:
            diagnostics["source_http_status"] = int(http_status)
        except (TypeError, ValueError):
            diagnostics["source_http_status"] = None
    return diagnostics


def _dexscreener_exact_pair_no_match_result(
    *,
    request_kind: str,
    measured_payload: Mapping[str, Any],
    payload: Mapping[str, Any],
    reason: str,
    pairs_present: bool,
    pairs_value: Any,
) -> NormalizedSourceResult:
    """Lawful exact-pair no-match: PARTIAL, no fabricated liquidity, bounded diag."""
    diagnostics = _dexscreener_pairs_schema_diagnostics(
        payload,
        request_kind=request_kind,
        measured_payload=measured_payload,
    )
    # Empty kept set — never invent a pair/liquidity row from a no-match.
    diagnostics["pairs"] = []
    diagnostics["no_matching_pairs"] = True
    diagnostics["no_matching_pairs_reason"] = reason
    diagnostics["pairs_field_present"] = bool(pairs_present)
    diagnostics["pairs_field_type"] = _pairs_field_type_label(
        pairs_value, present=pairs_present
    )
    if pairs_present and isinstance(pairs_value, list):
        diagnostics["pairs_count"] = 0
    elif not pairs_present:
        diagnostics["pairs_count"] = None
    else:
        # null / non-list lawful only when already accepted as no-match
        diagnostics["pairs_count"] = 0
    return NormalizedSourceResult(
        source_name=DEXSCREENER_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.PARTIAL,
        data_quality_label=DataQualityLabel.ACCEPTABLE_PARTIAL_DATA,
        normalized_payload=MappingProxyType(diagnostics),
    )


def normalize_dexscreener_fixture_result(
    payload: Mapping[str, Any],
    *,
    request_kind: str,
    requested_token_mints: Sequence[str] | None = None,
) -> NormalizedSourceResult:
    from printer_v1.sources.measured_transport import merge_transport_payload_metadata

    fixture_status = payload.get("fixture_status")
    measured_meta = merge_transport_payload_metadata(payload)
    measured_payload = {
        "transport_operations_used": measured_meta["transport_operations_used"],
        "response_bytes": measured_meta["response_bytes"],
        "normalized_rows": measured_meta["normalized_rows"],
        "transport_operation_identities": measured_meta[
            "transport_operation_identities"
        ],
    }
    if fixture_status == "failure":
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type=str(payload.get("failure_type") or "dexscreener_fixture_failure"),
            failure_message=str(payload.get("failure_message") or "DexScreener fixture failure"),
            normalized_payload=MappingProxyType(measured_payload),
        )
    if fixture_status == "rate_limited":
        retry_after = int(payload.get("retry_after_seconds") or 60)
        retry_at = (datetime.now(timezone.utc) + timedelta(seconds=retry_after)).isoformat()
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.STALE,
            data_quality_label=DataQualityLabel.STALE_DATA,
            failure_type="dexscreener_rate_limited_fixture",
            failure_message="DexScreener fixture rate limit",
            retry_after_at=retry_at,
            normalized_payload=MappingProxyType(measured_payload),
        )

    pairs_present = "pairs" in payload
    pairs = payload.get("pairs") if pairs_present else None
    exact_pair_request = _is_exact_pair_request_kind(request_kind)

    # Exact-pair endpoint only (live evidence 20260804T005054Z): HTTP 200 with
    # pairs:null is a lawful no-match, not a schema failure. pairs:[] already was.
    # Missing pairs is lawful no-match only under the pinned success envelope.
    if exact_pair_request and pairs_present and pairs is None:
        return _dexscreener_exact_pair_no_match_result(
            request_kind=request_kind,
            measured_payload=measured_payload,
            payload=payload,
            reason="source_returned_null_pairs",
            pairs_present=True,
            pairs_value=None,
        )
    if (
        exact_pair_request
        and not pairs_present
        and _exact_pair_success_envelope(payload)
    ):
        return _dexscreener_exact_pair_no_match_result(
            request_kind=request_kind,
            measured_payload=measured_payload,
            payload=payload,
            reason="source_omitted_pairs_under_success_envelope",
            pairs_present=False,
            pairs_value=None,
        )

    if not isinstance(pairs, list):
        diagnostics = _dexscreener_pairs_schema_diagnostics(
            payload,
            request_kind=request_kind,
            measured_payload=measured_payload,
        )
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type="dexscreener_malformed_fixture",
            failure_message="DexScreener fixture missing pairs",
            normalized_payload=MappingProxyType(diagnostics),
        )
    # Fail closed on provider-controlled multi-row arrays above declared ceiling.
    from printer_v1.sources.measured_transport import (
        MeasuredTransportError,
        ROW_CEILINGS,
        enforce_normalized_row_ceiling,
        merge_transport_payload_metadata,
    )

    row_kind = (
        "dexscreener_fresh_profile_mints"
        if "fresh" in str(request_kind).casefold()
        else "dexscreener_exact_pair_rows"
    )
    # Fresh-profile token batch may fan out to multiple pairs per mint; bound
    # total rows at mint ceiling * 4 without raising the exact-pair snapshot.
    declared = dict(ROW_CEILINGS)
    if row_kind == "dexscreener_fresh_profile_mints":
        declared["dexscreener_fresh_profile_mints"] = (
            int(ROW_CEILINGS["dexscreener_fresh_profile_mints"]) * 4
        )
    try:
        enforce_normalized_row_ceiling(
            row_kind if row_kind in declared else "dexscreener_exact_pair_rows",
            len(pairs),
            declared=declared,
        )
    except MeasuredTransportError as exc:
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type="dexscreener_row_ceiling",
            failure_message=str(exc),
        )
    if not pairs:
        return _dexscreener_exact_pair_no_match_result(
            request_kind=request_kind,
            measured_payload=measured_payload,
            payload=payload,
            reason="source_returned_empty_pairs",
            pairs_present=True,
            pairs_value=pairs,
        ) if exact_pair_request else NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.PARTIAL,
            data_quality_label=DataQualityLabel.ACCEPTABLE_PARTIAL_DATA,
            normalized_payload=MappingProxyType({
                **dict(measured_payload),
                "pairs": [],
                "no_matching_pairs": True,
                "no_matching_pairs_reason": "source_returned_empty_pairs",
                "pairs_field_present": True,
                "pairs_field_type": "LIST",
                "pairs_count": 0,
                "request_kind": str(request_kind),
            }),
        )

    normalized_pairs = []
    requested = {str(item) for item in (requested_token_mints or ()) if item}
    for pair in pairs:
        if not isinstance(pair, Mapping):
            continue
        base = pair.get("baseToken") if isinstance(pair.get("baseToken"), Mapping) else {}
        quote = pair.get("quoteToken") if isinstance(pair.get("quoteToken"), Mapping) else {}
        base_mint = str(base.get("address") or "")
        quote_mint = str(quote.get("address") or "")
        candidate_mint = base_mint
        if requested:
            candidate_mint = (
                base_mint if base_mint in requested
                else quote_mint if quote_mint in requested
                else ""
            )
        normalized_pairs.append(
            {
                "chain": pair.get("chainId"),
                "pair_address": pair.get("pairAddress"),
                "token_mint": base.get("address"),
                "candidate_mint": candidate_mint or None,
                "candidate_pair_orientation_status": (
                    "PASS" if candidate_mint and candidate_mint == base_mint else "FAIL"
                ),
                "candidate_pair_orientation_reason": (
                    None if candidate_mint and candidate_mint == base_mint
                    else "BASE_QUOTE_ORIENTATION_MISMATCH"
                ),
                # Preserve the provider's exact orientation.  Candidate
                # admission must never reconstruct quote identity from venue,
                # symbol, or a default native mint.
                "base_mint": base.get("address"),
                "quote_mint": quote.get("address"),
                "dex_id": pair.get("dexId"),
                "symbol": base.get("symbol"),
                "name": base.get("name"),
                "price_usd": _to_float(pair.get("priceUsd")),
                "liquidity_usd": _to_float((pair.get("liquidity") or {}).get("usd") if isinstance(pair.get("liquidity"), Mapping) else None),
                "volume_5m": _to_float((pair.get("volume") or {}).get("m5") if isinstance(pair.get("volume"), Mapping) else None),
                "volume_1h": _to_float((pair.get("volume") or {}).get("h1") if isinstance(pair.get("volume"), Mapping) else None),
                "volume_24h": _to_float((pair.get("volume") or {}).get("h24") if isinstance(pair.get("volume"), Mapping) else None),
                "txns_5m": _to_int(_transaction_count((pair.get("txns") or {}).get("m5") if isinstance(pair.get("txns"), Mapping) else None)),
                "txns_1h": _to_int(_transaction_count((pair.get("txns") or {}).get("h1") if isinstance(pair.get("txns"), Mapping) else None)),
                "txns_24h": _to_int(_transaction_count((pair.get("txns") or {}).get("h24") if isinstance(pair.get("txns"), Mapping) else None)),
                "buys_5m": _transaction_buys((pair.get("txns") or {}).get("m5") if isinstance(pair.get("txns"), Mapping) else None),
                "sells_5m": _transaction_sells((pair.get("txns") or {}).get("m5") if isinstance(pair.get("txns"), Mapping) else None),
                "buys_1h": _transaction_buys((pair.get("txns") or {}).get("h1") if isinstance(pair.get("txns"), Mapping) else None),
                "sells_1h": _transaction_sells((pair.get("txns") or {}).get("h1") if isinstance(pair.get("txns"), Mapping) else None),
                "buys_24h": _transaction_buys((pair.get("txns") or {}).get("h24") if isinstance(pair.get("txns"), Mapping) else None),
                "sells_24h": _transaction_sells((pair.get("txns") or {}).get("h24") if isinstance(pair.get("txns"), Mapping) else None),
                "fdv": _to_float(pair.get("fdv")),
                "market_cap": _to_float(pair.get("marketCap")),
                "price_change_5m": _to_float((pair.get("priceChange") or {}).get("m5") if isinstance(pair.get("priceChange"), Mapping) else None),
                "price_change_1h": _to_float((pair.get("priceChange") or {}).get("h1") if isinstance(pair.get("priceChange"), Mapping) else None),
                "price_change_24h": _to_float((pair.get("priceChange") or {}).get("h24") if isinstance(pair.get("priceChange"), Mapping) else None),
                "pair_created_at": pair.get("pairCreatedAt"),
            }
        )

    # Categorical productivity/safety filter (Stage 2 repair): drop non-Solana
    # pairs and infrastructure quote-mints at the source boundary so the
    # downstream candidate stream carries only Solana memecoin candidates.
    # Every excluded pair is recorded with an explicit categorical reason —
    # never silently dropped. No scores, ranks, or weighted logic are applied.
    kept_pairs: list[dict[str, Any]] = []
    excluded_pairs: list[dict[str, Any]] = []
    for item in normalized_pairs:
        exclusion_reason: str | None = None
        if item.get("chain") != "solana":
            exclusion_reason = "non_solana_pair"
        elif not item.get("pair_address") or not (
            item.get("candidate_mint") or item.get("token_mint")
        ):
            exclusion_reason = "missing_pair_or_mint_identity"
        elif (
            item.get("candidate_mint") or item.get("token_mint")
        ) in _SOLANA_INFRASTRUCTURE_MINTS:
            exclusion_reason = "infrastructure_quote_mint"
        if exclusion_reason:
            excluded_pairs.append({
                "chain": item.get("chain"),
                "pair_address": item.get("pair_address"),
                "token_mint": item.get("candidate_mint") or item.get("token_mint"),
                "symbol": item.get("symbol"),
                "exclusion_reason": exclusion_reason,
            })
        else:
            kept_pairs.append(item)

    if not kept_pairs:
        return NormalizedSourceResult(
            source_name=DEXSCREENER_SOURCE_NAME,
            request_kind=request_kind,
            source_status=SourceStatus.FAILED,
            data_quality_label=DataQualityLabel.MISSING_CRITICAL_DATA,
            failure_type="dexscreener_missing_critical_fixture_fields",
            failure_message="DexScreener fixture missing Solana memecoin pair identity",
        )

    stale = bool(payload.get("fixture_stale"))
    measured = merge_transport_payload_metadata(payload)
    if not measured["transport_operation_identities"] and measured["transport_operations_used"] == 0:
        # Fixture/offline transports may omit identities; count zero actual RPC.
        measured = {
            "transport_operations_used": int(payload.get("transport_operations_used") or 0),
            "response_bytes": int(payload.get("response_bytes") or 0),
            "normalized_rows": len(kept_pairs),
            "transport_operation_identities": tuple(
                payload.get("transport_operation_identities") or ()
            ),
        }
    return NormalizedSourceResult(
        source_name=DEXSCREENER_SOURCE_NAME,
        request_kind=request_kind,
        source_status=SourceStatus.STALE if stale else SourceStatus.COMPLETE,
        data_quality_label=DataQualityLabel.STALE_DATA if stale else DataQualityLabel.CLEAN_DATA,
        normalized_payload=MappingProxyType(
            {
                "source_name": DEXSCREENER_SOURCE_NAME,
                "request_kind": request_kind,
                "pairs": kept_pairs,
                "excluded_pairs": excluded_pairs,
                "excluded_pair_count": len(excluded_pairs),
                "transport_operations_used": measured["transport_operations_used"],
                "response_bytes": measured["response_bytes"],
                "normalized_rows": measured["normalized_rows"] or len(kept_pairs),
                "transport_operation_identities": measured[
                    "transport_operation_identities"
                ],
            }
        ),
        status_code=int(payload.get("_source_status_code") or 200),
    )


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _transaction_count(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    buys = _to_int(value.get("buys")) or 0
    sells = _to_int(value.get("sells")) or 0
    return buys + sells


def _transaction_buys(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    return _to_int(value.get("buys"))


def _transaction_sells(value: Any) -> int | None:
    if not isinstance(value, Mapping):
        return None
    return _to_int(value.get("sells"))
