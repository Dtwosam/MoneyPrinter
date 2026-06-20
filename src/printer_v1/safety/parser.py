"""Local Safety / Rug payload parser for Printer V1."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.safety.contracts import SafetyPayloadQualityLabel


NORMALIZED_FIELDS = (
    "token_id",
    "pair_id",
    "token_mint",
    "pair_address",
    "captured_at",
    "liquidity_usd",
    "liquidity_locked",
    "liquidity_lock_source",
    "liquidity_lock_until",
    "holder_count",
    "top_holder_percent",
    "top_5_holder_percent",
    "top_10_holder_percent",
    "creator_percent",
    "mint_authority_present",
    "freeze_authority_present",
    "update_authority_present",
    "transfer_fee_present",
    "blacklist_function_present",
    "honeypot_like_behavior",
    "sell_restriction_detected",
    "buy_restriction_detected",
    "mutable_metadata",
    "suspicious_metadata",
    "suspicious_creator_activity",
    "source_name",
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
        if lowered in {"true", "yes", "1"}:
            return 1
        if lowered in {"false", "no", "0"}:
            return 0
    return 1 if bool(value) else 0


def extract_liquidity_safety_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("liquidity") if isinstance(payload.get("liquidity"), Mapping) else payload
    return {
        "liquidity_usd": to_float(context.get("liquidity_usd") or context.get("usd")),
        "liquidity_locked": to_bool_int(context.get("liquidity_locked") or context.get("locked")),
        "liquidity_lock_source": context.get("liquidity_lock_source") or context.get("lock_source"),
        "liquidity_lock_until": to_timestamp(context.get("liquidity_lock_until") or context.get("lock_until")),
    }


def extract_authority_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("authority") if isinstance(payload.get("authority"), Mapping) else payload
    return {
        "mint_authority_present": to_bool_int(context.get("mint_authority_present")),
        "freeze_authority_present": to_bool_int(context.get("freeze_authority_present")),
        "update_authority_present": to_bool_int(context.get("update_authority_present")),
        "transfer_fee_present": to_bool_int(context.get("transfer_fee_present")),
        "blacklist_function_present": to_bool_int(context.get("blacklist_function_present")),
    }


def extract_distribution_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("distribution") if isinstance(payload.get("distribution"), Mapping) else payload
    return {
        "holder_count": to_int(context.get("holder_count")),
        "top_holder_percent": to_float(context.get("top_holder_percent")),
        "top_5_holder_percent": to_float(context.get("top_5_holder_percent")),
        "top_10_holder_percent": to_float(context.get("top_10_holder_percent")),
        "creator_percent": to_float(context.get("creator_percent")),
    }


def extract_restriction_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    context = payload.get("restrictions") if isinstance(payload.get("restrictions"), Mapping) else payload
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), Mapping) else payload
    creator = payload.get("creator") if isinstance(payload.get("creator"), Mapping) else payload
    return {
        "honeypot_like_behavior": to_bool_int(context.get("honeypot_like_behavior")),
        "sell_restriction_detected": to_bool_int(context.get("sell_restriction_detected")),
        "buy_restriction_detected": to_bool_int(context.get("buy_restriction_detected")),
        "mutable_metadata": to_bool_int(metadata.get("mutable_metadata")),
        "suspicious_metadata": to_bool_int(metadata.get("suspicious_metadata")),
        "suspicious_creator_activity": to_bool_int(
            creator.get("suspicious_creator_activity")
        ),
    }


def normalize_safety_payload(
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
        extract_liquidity_safety_context(payload),
        extract_authority_context(payload),
        extract_distribution_context(payload),
        extract_restriction_context(payload),
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
        "liquidity_usd",
        "top_holder_percent",
        "top_5_holder_percent",
        "top_10_holder_percent",
        "creator_percent",
    ):
        normalized[field] = to_float(normalized.get(field))
    for field in ("token_id", "pair_id", "holder_count"):
        normalized[field] = to_int(normalized.get(field))
    for field in (
        "liquidity_locked",
        "mint_authority_present",
        "freeze_authority_present",
        "update_authority_present",
        "transfer_fee_present",
        "blacklist_function_present",
        "honeypot_like_behavior",
        "sell_restriction_detected",
        "buy_restriction_detected",
        "mutable_metadata",
        "suspicious_metadata",
        "suspicious_creator_activity",
    ):
        normalized[field] = to_bool_int(normalized.get(field))
    return normalized


def safety_payload_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_time = bool(payload.get("captured_at"))
    has_identity = bool(payload.get("token_id") or payload.get("token_mint"))
    has_context = any(
        payload.get(field) is not None
        for field in (
            "liquidity_usd",
            "mint_authority_present",
            "top_holder_percent",
            "sell_restriction_detected",
        )
    )
    return has_time and has_identity and has_context


def safety_payload_is_stale(
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


def validate_safety_payload(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> SafetyPayloadQualityLabel:
    from printer_v1.safety.classifier import classify_safety_payload_quality

    return classify_safety_payload_quality(normalize_safety_payload(payload, now), now)
