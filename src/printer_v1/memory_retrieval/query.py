"""Retrieval query helpers for local Printer memory evidence."""

from datetime import datetime, timezone
from typing import Any, Mapping

from printer_v1.contracts.enums import DataQualityLabel, SourceStatus
from printer_v1.memory_retrieval.contracts import RetrievalQueryTypeLabel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def build_current_setup_query_payload(
    *,
    token_id: int | None = None,
    pair_id: int | None = None,
    token_mint: str | None = None,
    pair_address: str | None = None,
    context: Mapping[str, Any] | None = None,
    query_at: datetime | None = None,
) -> dict[str, Any]:
    return {
        "query_type": RetrievalQueryTypeLabel.CURRENT_SETUP_QUERY.value,
        "token_id": token_id,
        "pair_id": pair_id,
        "token_mint": token_mint,
        "pair_address": pair_address,
        "query_at": (query_at or utc_now()).isoformat(),
        "context": dict(context or {}),
        "source_status": (context or {}).get("source_status", SourceStatus.COMPLETE.value),
        "data_quality_label": (context or {}).get("data_quality_label", DataQualityLabel.CLEAN_DATA.value),
    }


def normalize_retrieval_query_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized["query_type"] = RetrievalQueryTypeLabel(normalized.get("query_type") or RetrievalQueryTypeLabel.CURRENT_SETUP_QUERY).value
    normalized["source_status"] = SourceStatus(normalized.get("source_status") or SourceStatus.COMPLETE).value
    normalized["data_quality_label"] = DataQualityLabel(normalized.get("data_quality_label") or DataQualityLabel.CLEAN_DATA).value
    normalized.setdefault("context", {})
    normalized.setdefault("query_at", utc_now().isoformat())
    return normalized


def query_has_required_fields(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("token_id") or payload.get("token_mint"))


def query_context_is_clean_enough(payload: Mapping[str, Any]) -> bool:
    normalized = normalize_retrieval_query_payload(payload)
    return (
        SourceStatus(normalized["source_status"]) == SourceStatus.COMPLETE
        and DataQualityLabel(normalized["data_quality_label"]) == DataQualityLabel.CLEAN_DATA
    )


def validate_retrieval_query_payload(payload: Mapping[str, Any]) -> bool:
    normalized = normalize_retrieval_query_payload(payload)
    return query_has_required_fields(normalized)
