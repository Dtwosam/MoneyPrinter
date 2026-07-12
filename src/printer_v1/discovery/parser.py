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
    # V2-2H.3: timestamp, age, and price-change fields (100% missing in live audit)
    "pair_created_at",
    "token_created_at",
    "pair_age_seconds",
    "token_age_seconds",
    "price_change_5m",
    "price_change_15m",
    "price_change_1h",
    "price_change_24h",
    "price_change_15m_source_kind",
    "price_change_15m_provenance",
    "volume_15m_source_kind",
    "volume_15m_provenance",
    "txns_15m_source_kind",
    "txns_15m_completeness",
    "txns_15m_provenance",
    "market_15m_evidence_requests",
    "market_15m_evidence_pool_address",
    # V2-2P: T4-safe pair-age context labels; token_age_evidence_tier always None until T1/T2/T3 source active.
    "pair_age_context_label",
    "token_age_evidence_tier",
    "t3_requested_mint",
    "t3_rpc_host_redacted",
    "t3_rpc_methods_attempted",
    "t3_request_ids",
    "t3_pages_fetched",
    "t3_signatures_inspected",
    "t3_accepted_signature",
    "t3_accepted_slot",
    "t3_block_time_raw",
    "t3_block_time_source",
    "t3_instruction_type",
    "t3_token_program",
    "t3_derived_token_created_at",
    "t3_derived_token_age_seconds",
    "t3_captured_at",
    "t3_commitment",
    "t3_finality_status",
    "t3_source_request_id",
    "t3_source_response_id",
    "t3_source_failure_id",
    "t3_discovery_source_response_id",
    "a4_evidence_status",
    "a4_evidence_reason",
    "a4_prior_bucket",
    "a4_prior_discovery_candidate_id",
    "a4_prior_source_name",
    "a4_prior_source_channel",
    "a4_prior_source_request_id",
    "a4_prior_source_response_id",
    "a4_prior_source_status",
    "a4_prior_data_quality_label",
    "a4_prior_observed_at",
    "a4_current_source_request_id",
    "a4_current_source_response_id",
    "a4_current_source_status",
    "a4_current_data_quality_label",
    "a4_current_observed_at",
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


def _derive_pair_age_context_label(
    token_age_seconds: float | None,
    pair_age_seconds: float | None,
) -> str:
    """Return a T4-safe context label describing what age evidence is available.

    MUST NOT be used to drive derive_age_bucket, derive_recent_active_tier,
    or A3. It is reporting/context only. Pair age never replaces token age.
    """
    if token_age_seconds is not None:
        return "RECENT_LAUNCH" if token_age_seconds < 86400.0 else "OLDER_TOKEN"
    if pair_age_seconds is None:
        return "UNKNOWN_TOKEN_AGE"
    return "RECENT_PAIR_FOR_EXISTING_TOKEN" if pair_age_seconds < 86400.0 else "PAIR_ONLY_AGE_KNOWN"


def _derive_token_age_evidence_tier(
    source_name: str,
    candidate_payload: Mapping[str, Any],
    token_created_at_raw: Any,
    token_age_seconds: float | None,
) -> str | None:
    """Return the token-age evidence tier for this candidate.

    T2: source is pumpportal, request_kind is pumpfun_launch_stream,
        explicit source-provided timestamp present and valid age derived.

    OBSERVED_LIVE_LAUNCH: source is pumpportal, request_kind is
        pumpfun_launch_stream, no explicit timestamp field existed in the
        event, live_observed_launch flag set by pumpportal normalizer.
        token_created_at and token_age_seconds remain None.

    T3: source is solana_rpc, request_kind is mint_creation_time_reference,
        governed RPC mint-creation evidence confirmed; both token_created_at
        and token_age_seconds set from on-chain block time.

    All other cases return None (T5 unknown).
    T2 takes precedence over OBSERVED_LIVE_LAUNCH if both conditions could apply.
    """
    if candidate_payload.get("token_age_evidence_tier") == "T3" and source_name != "solana_rpc":
        token_mint = candidate_payload.get("token_mint") or candidate_payload.get("mint")
        if (
            token_created_at_raw is not None
            and token_age_seconds is not None
            and token_mint
            and candidate_payload.get("t3_requested_mint") == token_mint
            and candidate_payload.get("t3_commitment") == "finalized"
            and candidate_payload.get("t3_finality_status") == "finalized"
            and candidate_payload.get("t3_source_response_id") is not None
            and candidate_payload.get("t3_source_failure_id") is None
        ):
            return "T3"
        return None
    if source_name == "pumpportal":
        if candidate_payload.get("request_kind") != "pumpfun_launch_stream":
            return None
        # T2: explicit source-provided timestamp present and valid.
        if token_created_at_raw is not None and token_age_seconds is not None:
            return "T2"
        # OBSERVED_LIVE_LAUNCH: mint-bearing launch event; no explicit timestamp field.
        if token_created_at_raw is None and candidate_payload.get("live_observed_launch"):
            return "OBSERVED_LIVE_LAUNCH"
        return None
    if source_name == "solana_rpc":
        if candidate_payload.get("request_kind") != "mint_creation_time_reference":
            return None
        # T3: governed RPC mint-creation evidence; both values required.
        if token_created_at_raw is not None and token_age_seconds is not None:
            return "T3"
        return None
    return None


def normalize_candidate(
    source_name: str,
    candidate_payload: Mapping[str, Any],
    now: datetime | None = None,
) -> dict[str, Any]:
    if source_name not in SOURCE_REGISTRY:
        raise ValueError(f"Unknown discovery source: {source_name}")

    _now = now if now is not None else datetime.now(timezone.utc)

    base_token = candidate_payload.get("baseToken") or {}
    quote_token = candidate_payload.get("quoteToken") or {}
    attributes = candidate_payload.get("attributes") or {}
    relationships = candidate_payload.get("relationships") or {}

    captured_at = first_present(
        candidate_payload,
        attributes,
        keys=("captured_at", "capturedAt", "createdAt", "created_at", "updated_at"),
    )

    # Timestamp fields — extract raw values; age is derived below.
    _pair_created_at_raw = first_present(
        candidate_payload,
        attributes,
        keys=("pair_created_at", "pairCreatedAt", "pool_created_at", "poolCreatedAt"),
    )
    _token_created_at_raw = first_present(
        candidate_payload,
        attributes,
        keys=("token_created_at", "tokenCreatedAt"),
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
        # V2-2H.3: timestamp, age, and price-change fields.
        # Stored as-is (string or None); age is a derived float, not guessed from zero.
        "pair_created_at": str(_pair_created_at_raw) if _pair_created_at_raw is not None else None,
        "token_created_at": str(_token_created_at_raw) if _token_created_at_raw is not None else None,
        "pair_age_seconds": _safe_age_seconds(_pair_created_at_raw, _now),
        "token_age_seconds": _safe_age_seconds(_token_created_at_raw, _now),
        "price_change_5m": nested_numeric(
            candidate_payload, attributes,
            key_paths=(("priceChange", "m5"), ("price_change", "m5"), ("price_change_5m",)),
        ),
        "price_change_15m": nested_numeric(
            candidate_payload, attributes,
            key_paths=(("priceChange", "m15"), ("price_change", "m15"), ("price_change_15m",)),
        ),
        "price_change_1h": nested_numeric(
            candidate_payload, attributes,
            key_paths=(("priceChange", "h1"), ("price_change", "h1"), ("price_change_1h",)),
        ),
        "price_change_24h": nested_numeric(
            candidate_payload, attributes,
            key_paths=(("priceChange", "h24"), ("price_change", "h24"), ("price_change_24h",)),
        ),
        "price_change_15m_source_kind": candidate_payload.get("price_change_15m_source_kind"),
        "price_change_15m_provenance": candidate_payload.get("price_change_15m_provenance"),
        "volume_15m_source_kind": candidate_payload.get("volume_15m_source_kind"),
        "volume_15m_provenance": candidate_payload.get("volume_15m_provenance"),
        "txns_15m_source_kind": candidate_payload.get("txns_15m_source_kind"),
        "txns_15m_completeness": candidate_payload.get("txns_15m_completeness"),
        "txns_15m_provenance": candidate_payload.get("txns_15m_provenance"),
        "market_15m_evidence_requests": candidate_payload.get("market_15m_evidence_requests"),
        "market_15m_evidence_pool_address": candidate_payload.get("market_15m_evidence_pool_address"),
        # V2-2P: T4-safe pair-age context. Never drives age gates or A3.
        "pair_age_context_label": _derive_pair_age_context_label(
            _safe_age_seconds(_token_created_at_raw, _now),
            _safe_age_seconds(_pair_created_at_raw, _now),
        ),
        "token_age_evidence_tier": _derive_token_age_evidence_tier(
            source_name,
            candidate_payload,
            _token_created_at_raw,
            _safe_age_seconds(_token_created_at_raw, _now),
        ),
        # Real T3 audit fields are copied verbatim after the T3 source normalizer
        # has validated the exact mint, finalized transaction, and block time.
        "t3_requested_mint": candidate_payload.get("t3_requested_mint"),
        "t3_rpc_host_redacted": candidate_payload.get("t3_rpc_host_redacted"),
        "t3_rpc_methods_attempted": candidate_payload.get("t3_rpc_methods_attempted"),
        "t3_request_ids": candidate_payload.get("t3_request_ids"),
        "t3_pages_fetched": candidate_payload.get("t3_pages_fetched"),
        "t3_signatures_inspected": candidate_payload.get("t3_signatures_inspected"),
        "t3_accepted_signature": candidate_payload.get("t3_accepted_signature"),
        "t3_accepted_slot": candidate_payload.get("t3_accepted_slot"),
        "t3_block_time_raw": candidate_payload.get("t3_block_time_raw"),
        "t3_block_time_source": candidate_payload.get("t3_block_time_source"),
        "t3_instruction_type": candidate_payload.get("t3_instruction_type"),
        "t3_token_program": candidate_payload.get("t3_token_program"),
        "t3_derived_token_created_at": candidate_payload.get("t3_derived_token_created_at"),
        "t3_derived_token_age_seconds": candidate_payload.get("t3_derived_token_age_seconds"),
        "t3_captured_at": candidate_payload.get("t3_captured_at"),
        "t3_commitment": candidate_payload.get("t3_commitment"),
        "t3_finality_status": candidate_payload.get("t3_finality_status"),
        "t3_source_request_id": candidate_payload.get("t3_source_request_id"),
        "t3_source_response_id": candidate_payload.get("t3_source_response_id"),
        "t3_source_failure_id": candidate_payload.get("t3_source_failure_id"),
        "t3_discovery_source_response_id": candidate_payload.get("t3_discovery_source_response_id"),
        # A4 evidence is produced only by the guarded prior/current DB handoff.
        "a4_evidence_status": candidate_payload.get("a4_evidence_status"),
        "a4_evidence_reason": candidate_payload.get("a4_evidence_reason"),
        "a4_prior_bucket": candidate_payload.get("a4_prior_bucket"),
        "a4_prior_discovery_candidate_id": candidate_payload.get("a4_prior_discovery_candidate_id"),
        "a4_prior_source_name": candidate_payload.get("a4_prior_source_name"),
        "a4_prior_source_channel": candidate_payload.get("a4_prior_source_channel"),
        "a4_prior_source_request_id": candidate_payload.get("a4_prior_source_request_id"),
        "a4_prior_source_response_id": candidate_payload.get("a4_prior_source_response_id"),
        "a4_prior_source_status": candidate_payload.get("a4_prior_source_status"),
        "a4_prior_data_quality_label": candidate_payload.get("a4_prior_data_quality_label"),
        "a4_prior_observed_at": candidate_payload.get("a4_prior_observed_at"),
        "a4_current_source_request_id": candidate_payload.get("a4_current_source_request_id"),
        "a4_current_source_response_id": candidate_payload.get("a4_current_source_response_id"),
        "a4_current_source_status": candidate_payload.get("a4_current_source_status"),
        "a4_current_data_quality_label": candidate_payload.get("a4_current_data_quality_label"),
        "a4_current_observed_at": candidate_payload.get("a4_current_observed_at"),
    }
    return {field: normalized.get(field) for field in NORMALIZED_FIELDS}


def normalize_candidates(
    source_name: str,
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    return [normalize_candidate(source_name, item, now) for item in extract_candidate_items(source_name, payload)]


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


def _parse_created_at(value: Any) -> datetime | None:
    """Parse a created_at/created timestamp to UTC datetime, or None if unparseable.

    Handles ISO-8601 strings and Unix epoch integers. DexScreener uses epoch
    milliseconds (values > 1e10); other sources use epoch seconds.
    """
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        try:
            epoch_s = float(value) / 1000.0 if float(value) > 1e10 else float(value)
            return datetime.fromtimestamp(epoch_s, tz=timezone.utc)
        except (ValueError, OverflowError, OSError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
        except (ValueError, TypeError):
            return None
    return None


def _safe_age_seconds(created_at: Any, now: datetime) -> float | None:
    """Derive age in seconds from a created_at value and reference time.

    Returns None for missing, unparseable, or future timestamps. A future
    timestamp (negative age) indicates clock skew or bad data — it must not
    produce a near-zero age that looks like a freshly created token/pair.
    """
    dt = _parse_created_at(created_at)
    if dt is None:
        return None
    age = (now - dt).total_seconds()
    return age if age >= 0.0 else None
