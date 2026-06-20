"""Deterministic snapshot quality helpers."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.lifecycle.contracts import TokenLifecycleState
from printer_v1.snapshots.contracts import QuoteRouteStatus, SnapshotMode, SnapshotQualityLabel


REQUIRED_FIELDS = (
    "captured_at",
    "tracking_lane",
    "snapshot_mode",
    "price_usd",
    "liquidity_usd",
    "source_status",
    "data_quality_label",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def parse_timestamp(value: datetime | str | None) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc)
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(timezone.utc)


def to_timestamp(value: datetime | str | None) -> str | None:
    parsed = parse_timestamp(value)
    return parsed.isoformat() if parsed else None


def candidate_snapshot_has_required_fields(payload: Mapping[str, Any]) -> bool:
    has_token = bool(payload.get("token_id") or payload.get("token_mint"))
    has_pair = bool(payload.get("pair_id") or payload.get("pair_address"))
    if not has_token or not has_pair:
        return False
    return all(payload.get(field) is not None for field in REQUIRED_FIELDS)


def validate_snapshot_payload(payload: Mapping[str, Any]) -> SnapshotQualityLabel:
    if not candidate_snapshot_has_required_fields(payload):
        return SnapshotQualityLabel.MISSING_CRITICAL_FIELDS
    return classify_snapshot_quality(payload)


def is_snapshot_stale(
    captured_at: datetime | str | None,
    now: datetime | None,
    stale_after_seconds: int,
) -> bool:
    captured = parse_timestamp(captured_at)
    if captured is None:
        return True
    current_time = now or utc_now()
    return (current_time - captured).total_seconds() > stale_after_seconds


def classify_snapshot_source_state(
    source_status: SourceStatus | str,
    data_quality_label: DataQualityLabel | str,
) -> SnapshotQualityLabel:
    status = SourceStatus(source_status)
    quality = DataQualityLabel(data_quality_label)
    if status == SourceStatus.CONFLICTING or quality == DataQualityLabel.CONFLICTING_DATA:
        return SnapshotQualityLabel.CONFLICTING_SNAPSHOT
    if status == SourceStatus.STALE or quality == DataQualityLabel.STALE_DATA:
        return SnapshotQualityLabel.STALE_SNAPSHOT
    if quality in {
        DataQualityLabel.DIRTY_DATA,
        DataQualityLabel.MISSING_CRITICAL_DATA,
        DataQualityLabel.DO_NOT_TRAIN,
    } or status == SourceStatus.FAILED:
        return SnapshotQualityLabel.DIRTY_SNAPSHOT
    if status == SourceStatus.PARTIAL or quality == DataQualityLabel.ACCEPTABLE_PARTIAL_DATA:
        return SnapshotQualityLabel.PARTIAL_SNAPSHOT
    return SnapshotQualityLabel.CLEAN_SNAPSHOT


def classify_snapshot_quality(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> SnapshotQualityLabel:
    if not candidate_snapshot_has_required_fields(payload):
        return SnapshotQualityLabel.MISSING_CRITICAL_FIELDS
    source_state = classify_snapshot_source_state(
        payload["source_status"],
        payload["data_quality_label"],
    )
    if source_state != SnapshotQualityLabel.CLEAN_SNAPSHOT:
        return source_state
    if is_snapshot_stale(payload["captured_at"], now, stale_after_seconds=900):
        return SnapshotQualityLabel.STALE_SNAPSHOT
    missing_noncritical = any(
        payload.get(field) is None
        for field in ("volume_5m", "volume_15m", "txns_5m", "txns_15m")
    )
    if missing_noncritical:
        return SnapshotQualityLabel.PARTIAL_SNAPSHOT
    return SnapshotQualityLabel.CLEAN_SNAPSHOT


def snapshot_can_support_clean_memory(
    payload: Mapping[str, Any],
    now: datetime | None = None,
) -> bool:
    return classify_snapshot_quality(payload, now) in {
        SnapshotQualityLabel.CLEAN_SNAPSHOT,
        SnapshotQualityLabel.PARTIAL_SNAPSHOT,
    }


def normalize_number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    return float(value)


def normalize_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    return int(value)


def normalize_snapshot_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if "tracking_lane" in normalized and normalized["tracking_lane"] is not None:
        normalized["tracking_lane"] = TokenLifecycleState(normalized["tracking_lane"]).value
    if "snapshot_mode" in normalized and normalized["snapshot_mode"] is not None:
        normalized["snapshot_mode"] = SnapshotMode(normalized["snapshot_mode"]).value
    if "source_status" in normalized and normalized["source_status"] is not None:
        normalized["source_status"] = SourceStatus(normalized["source_status"]).value
    if "data_quality_label" in normalized and normalized["data_quality_label"] is not None:
        normalized["data_quality_label"] = DataQualityLabel(
            normalized["data_quality_label"]
        ).value
    normalized["captured_at"] = to_timestamp(normalized.get("captured_at"))
    normalized.setdefault("quote_status", QuoteRouteStatus.QUOTE_NOT_REQUIRED.value)
    normalized.setdefault("route_status", QuoteRouteStatus.QUOTE_NOT_REQUIRED.value)

    for field in (
        "price_usd",
        "price_native",
        "liquidity_usd",
        "volume_5m",
        "volume_15m",
        "volume_1h",
        "volume_4h",
        "volume_12h",
        "volume_24h",
        "fdv",
        "market_cap",
        "price_change_5m",
        "price_change_15m",
        "price_change_1h",
        "price_change_4h",
        "price_change_12h",
        "price_change_24h",
    ):
        if field in normalized:
            normalized[field] = normalize_number(normalized[field])
    for field in (
        "token_id",
        "pair_id",
        "pair_age_seconds",
        "token_age_seconds",
        "txns_5m",
        "txns_15m",
        "txns_1h",
        "txns_4h",
        "txns_12h",
        "txns_24h",
    ):
        if field in normalized:
            normalized[field] = normalize_int(normalized[field])
    return normalized
